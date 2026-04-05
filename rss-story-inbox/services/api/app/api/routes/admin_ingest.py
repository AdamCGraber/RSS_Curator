from datetime import date, datetime, time, timedelta, timezone
from threading import Lock, Thread
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal, engine, get_db
from app.models.article import Article
from app.models.ingestion_job import IngestionJob
from app.models.user_preference import UserPreference
from app.models.profile import Profile
from app.services.cluster.clusterer import cluster_recent
from app.services.ingest.fetch_rss import fetch_feed
from app.services.rank.scorer import score_clusters
from app.services.sources_state import get_active_sources_snapshot
from app.services.filtering.terms import parse_terms, should_keep_article

router = APIRouter(tags=["admin"])


class IngestionJobStatus(BaseModel):
    job_id: str
    status: str
    started_at: str
    updated_at: str
    total_items: int
    processed_items: int
    progress_percent: float
    eta_seconds: int | None = None
    phase: str = "DISCOVERING_FEEDS"


class IngestionJobStartResponse(BaseModel):
    job_id: str
    status: str
    already_running: bool = False


class IngestSettings(BaseModel):
    cluster_similarity_threshold: float = Field(0.88, ge=0.0, le=1.0)
    cluster_time_window_days: int = Field(2, ge=1)
    start_date: date
    end_date: date


class IngestRequest(BaseModel):
    cluster_similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    cluster_time_window_days: int | None = Field(default=None, ge=1)
    start_date: date | None = None
    end_date: date | None = None


_ingest_lock = Lock()
ORPHANED_RUNNING_JOB_TIMEOUT_SECONDS = 180
INGESTION_ADVISORY_LOCK_KEY = 98172341
INGESTION_PHASES = (
    "DISCOVERING_FEEDS",
    "IMPORTING_ITEMS",
    "CLUSTERING",
    "SCORING",
    "FINALIZING",
)

PHASE_1_MAX_PROGRESS = 65
PHASE_2_MAX_PROGRESS = 90
PHASE_3_MAX_PROGRESS = 95
PHASE_4_MAX_PROGRESS = 99


def _default_date_range(window_days: int) -> tuple[date, date]:
    utc_today = datetime.now(timezone.utc).date()
    end_date = utc_today - timedelta(days=1)
    start_date = end_date - timedelta(days=max(1, window_days) - 1)
    return start_date, end_date


def _window_days_from_range(start_date: date, end_date: date) -> int:
    return max(1, (end_date - start_date).days + 1)


def _normalize_range_to_utc_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    # Date semantics are inclusive on both ends: [start_date 00:00:00, end_date 23:59:59.999999].
    start_datetime = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_datetime = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
    return start_datetime, end_datetime


def _rolling_window_bounds(window_days: int) -> tuple[datetime, datetime]:
    end_datetime = datetime.now(timezone.utc)
    start_datetime = end_datetime - timedelta(days=max(1, window_days))
    return start_datetime, end_datetime


def _validate_date_range(start_date: date, end_date: date):
    utc_today = datetime.now(timezone.utc).date()
    if start_date >= utc_today or end_date >= utc_today:
        raise HTTPException(status_code=422, detail="start_date and end_date must both be in the past (before today UTC).")
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date.")


def ensure_preferences(db: Session) -> UserPreference:
    default_window_days = max(1, int(settings.cluster_time_window_hours / 24) or 2)
    default_start_date, default_end_date = _default_date_range(default_window_days)

    stmt = (
        insert(UserPreference)
        .values(
            user_id=1,
            cluster_similarity_threshold=0.88,
            cluster_time_window_days=default_window_days,
            cluster_time_window_start=default_start_date,
            cluster_time_window_end=default_end_date,
        )
        .on_conflict_do_nothing(index_elements=["user_id"])
    )
    db.execute(stmt)
    db.commit()

    prefs = db.query(UserPreference).filter(UserPreference.user_id == 1).first()
    if not prefs:
        raise HTTPException(status_code=500, detail="Failed to initialize ingest preferences")

    if prefs.cluster_time_window_start is None or prefs.cluster_time_window_end is None:
        derived_start, derived_end = _default_date_range(prefs.cluster_time_window_days)
        prefs.cluster_time_window_start = derived_start
        prefs.cluster_time_window_end = derived_end
        db.commit()
        db.refresh(prefs)

    return prefs


def _derive_phase(job: IngestionJob) -> str:
    if job.status == "COMPLETED":
        return INGESTION_PHASES[-1]

    progress = job.progress_percent or 0
    if progress < PHASE_1_MAX_PROGRESS:
        return "DISCOVERING_FEEDS"
    if progress < PHASE_2_MAX_PROGRESS:
        return "IMPORTING_ITEMS"
    if progress < PHASE_3_MAX_PROGRESS:
        return "CLUSTERING"
    if progress < PHASE_4_MAX_PROGRESS:
        return "SCORING"
    return "FINALIZING"


def _as_status(job: IngestionJob) -> IngestionJobStatus:
    return IngestionJobStatus(
        job_id=str(job.id),
        status=job.status,
        started_at=job.started_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        total_items=job.total_items,
        processed_items=job.processed_items,
        progress_percent=job.progress_percent,
        eta_seconds=None,
        phase=_derive_phase(job),
    )


def _get_running_job(db: Session) -> IngestionJob | None:
    return (
        db.query(IngestionJob)
        .filter(IngestionJob.status == "RUNNING")
        .order_by(IngestionJob.started_at.desc())
        .first()
    )


def _get_latest_job(db: Session) -> IngestionJob | None:
    return db.query(IngestionJob).order_by(IngestionJob.started_at.desc()).first()


def _is_worker_alive_via_advisory_lock() -> bool:
    if engine.dialect.name != "postgresql":
        return False

    with engine.connect() as conn:
        acquired = conn.execute(
            text("SELECT pg_try_advisory_lock(:lock_key)"),
            {"lock_key": INGESTION_ADVISORY_LOCK_KEY},
        ).scalar()

        if acquired:
            conn.execute(
                text("SELECT pg_advisory_unlock(:lock_key)"),
                {"lock_key": INGESTION_ADVISORY_LOCK_KEY},
            )
            return False

        return True


def _acquire_worker_advisory_lock():
    if engine.dialect.name != "postgresql":
        return None

    conn = engine.connect()
    acquired = conn.execute(
        text("SELECT pg_try_advisory_lock(:lock_key)"),
        {"lock_key": INGESTION_ADVISORY_LOCK_KEY},
    ).scalar()
    if not acquired:
        conn.close()
        raise RuntimeError("Another ingestion worker already owns the advisory lock")

    return conn


def _release_worker_advisory_lock(conn):
    if conn is None:
        return

    try:
        conn.execute(
            text("SELECT pg_advisory_unlock(:lock_key)"),
            {"lock_key": INGESTION_ADVISORY_LOCK_KEY},
        )
    finally:
        conn.close()


def _touch_job(db: Session, job: IngestionJob):
    job.updated_at = datetime.now(timezone.utc)
    db.commit()


def _set_phase_progress(
    db: Session,
    job: IngestionJob,
    phase: str,
    progress_percent: int,
    processed_items: int = 0,
    total_items: int | None = None,
    commit: bool = True,
):
    job.processed_items = max(0, processed_items)
    if total_items is not None:
        job.total_items = max(0, total_items)
    job.progress_percent = max(0, min(100, progress_percent))
    job.updated_at = datetime.now(timezone.utc)
    if commit:
        db.commit()


def _phase_1_progress(discovered_feed_count: int, total_sources: int) -> int:
    if total_sources <= 0:
        return PHASE_1_MAX_PROGRESS
    ratio = max(0.0, min(1.0, discovered_feed_count / total_sources))
    return int(round(ratio * PHASE_1_MAX_PROGRESS))


def _phase_2_progress(processed_items: int, total_items: int) -> int:
    if total_items <= 0:
        return PHASE_2_MAX_PROGRESS
    ratio = max(0.0, min(1.0, processed_items / total_items))
    return int(round(PHASE_1_MAX_PROGRESS + ratio * (PHASE_2_MAX_PROGRESS - PHASE_1_MAX_PROGRESS)))


def _count_distinct_clusters_for_urls(db: Session, urls: list[str], chunk_size: int = 500) -> int:
    if not urls:
        return 0

    cluster_ids: set[int] = set()
    for i in range(0, len(urls), chunk_size):
        chunk = urls[i : i + chunk_size]
        rows = (
            db.query(Article.cluster_id)
            .filter(Article.url.in_(chunk), Article.cluster_id.is_not(None))
            .distinct()
            .all()
        )
        cluster_ids.update(int(cluster_id) for (cluster_id,) in rows if cluster_id is not None)

    return len(cluster_ids)


def _recover_orphaned_running_job(db: Session, job: IngestionJob) -> bool:
    """Mark stale RUNNING jobs as FAILED so ingestion can be restarted.

    Jobs run on daemon threads in-process, so a process restart can strand RUNNING
    rows forever. If a RUNNING job has not updated for a safety window, treat it as
    orphaned and fail it.
    """
    now = datetime.now(timezone.utc)
    age_seconds = max(0.0, (now - job.updated_at).total_seconds())
    if age_seconds <= ORPHANED_RUNNING_JOB_TIMEOUT_SECONDS:
        return False

    if _is_worker_alive_via_advisory_lock():
        job.updated_at = now
        db.commit()
        return False

    job.status = "FAILED"
    job.updated_at = now
    db.commit()
    return True


def _recover_if_stale_running_job(db: Session, job: IngestionJob | None) -> IngestionJob | None:
    if not job or job.status != "RUNNING":
        return job

    with _ingest_lock:
        recovered = _recover_orphaned_running_job(db, job)
        if recovered:
            return None

    db.refresh(job)
    return job


def _mark_job_failed(db: Session, job: IngestionJob):
    db.refresh(job)
    job.status = "FAILED"
    job.updated_at = datetime.now(timezone.utc)
    db.commit()


def _mark_job_complete(db: Session, job: IngestionJob, imported_items_count: int):
    db.refresh(job)
    job.total_items = max(0, imported_items_count)
    job.processed_items = max(0, imported_items_count)
    job.progress_percent = 100
    job.status = "COMPLETED"
    job.updated_at = datetime.now(timezone.utc)
    db.commit()


def run_ingestion_job(job_id: UUID, threshold: float, start_datetime: datetime, end_datetime: datetime):
    db = SessionLocal()
    lock_conn = None
    try:
        lock_conn = _acquire_worker_advisory_lock()
        job = db.get(IngestionJob, job_id)
        if not job:
            return
        _set_phase_progress(db, job, phase=INGESTION_PHASES[0], progress_percent=0)

        snapshot = get_active_sources_snapshot(db)
        sources = snapshot.get("sources", [])
        total_sources = len(sources)

        profile = db.query(Profile).order_by(Profile.id.asc()).first()
        include_terms = parse_terms(profile.include_terms if profile else None)
        include_terms_2 = parse_terms(profile.include_terms_2 if profile else None)
        exclude_terms = parse_terms(profile.exclude_terms if profile else None)

        discovered_rows: list[dict] = []
        discovered_feed_count = 0
        for source in sources:
            _touch_job(db, job)
            items = fetch_feed(source["feed_url"])
            discovered_feed_count += 1
            _set_phase_progress(
                db,
                job,
                phase=INGESTION_PHASES[0],
                progress_percent=_phase_1_progress(discovered_feed_count, total_sources),
                processed_items=discovered_feed_count,
            )
            for item in items:
                url = item.get("url")
                if not url:
                    continue
                title = (item.get("title") or "")[:512]
                raw_excerpt = item.get("summary") or None
                keep_article = should_keep_article(
                    title=title,
                    excerpt=raw_excerpt,
                    include_terms=include_terms,
                    include_terms_2=include_terms_2,
                    exclude_terms=exclude_terms,
                )

                discovered_rows.append(
                    {
                        "source_id": source["id"],
                        "url": url,
                        "title": title,
                        "raw_excerpt": raw_excerpt,
                        "published_at": item.get("published_at"),
                        "status": "INBOX" if keep_article else "REJECTED",
                    }
                )

        _set_phase_progress(
            db,
            job,
            phase=INGESTION_PHASES[0],
            progress_percent=PHASE_1_MAX_PROGRESS,
            processed_items=discovered_feed_count,
        )

        run_urls = list(dict.fromkeys(str(row["url"]) for row in discovered_rows if row.get("url")))
        _set_phase_progress(
            db,
            job,
            phase=INGESTION_PHASES[1],
            progress_percent=PHASE_1_MAX_PROGRESS,
            total_items=len(discovered_rows),
        )
        processed_count = 0
        for row in discovered_rows:
            with db.begin_nested():
                stmt = insert(Article).values(row).on_conflict_do_nothing(index_elements=["url"])
                db.execute(stmt)

            processed_count += 1
            _set_phase_progress(
                db,
                job,
                phase=INGESTION_PHASES[1],
                progress_percent=_phase_2_progress(processed_count, len(discovered_rows)),
                processed_items=processed_count,
                total_items=len(discovered_rows),
                commit=(processed_count % 10 == 0 or processed_count == len(discovered_rows)),
            )

        _set_phase_progress(
            db,
            job,
            phase=INGESTION_PHASES[1],
            progress_percent=PHASE_2_MAX_PROGRESS,
            processed_items=processed_count,
            total_items=len(discovered_rows),
        )

        _set_phase_progress(db, job, phase=INGESTION_PHASES[2], progress_percent=PHASE_2_MAX_PROGRESS)
        cluster_recent(
            db,
            threshold=threshold,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
        )
        cluster_count = _count_distinct_clusters_for_urls(db, run_urls)
        _set_phase_progress(
            db,
            job,
            phase=INGESTION_PHASES[2],
            progress_percent=PHASE_3_MAX_PROGRESS,
            processed_items=cluster_count,
        )

        _set_phase_progress(db, job, phase=INGESTION_PHASES[3], progress_percent=PHASE_3_MAX_PROGRESS)
        score_clusters(db)
        scored_clusters = _count_distinct_clusters_for_urls(db, run_urls)
        _set_phase_progress(
            db,
            job,
            phase=INGESTION_PHASES[3],
            progress_percent=PHASE_4_MAX_PROGRESS,
            processed_items=scored_clusters,
        )

        _set_phase_progress(db, job, phase=INGESTION_PHASES[4], progress_percent=PHASE_4_MAX_PROGRESS)
        db.commit()

        _mark_job_complete(db, job, imported_items_count=processed_count)
    except Exception:
        db.rollback()
        job = db.get(IngestionJob, job_id)
        if job:
            _mark_job_failed(db, job)
    finally:
        _release_worker_advisory_lock(lock_conn)
        db.close()


@router.get("/admin/ingest/settings", response_model=IngestSettings)
def ingest_settings(db: Session = Depends(get_db)):
    prefs = ensure_preferences(db)
    _validate_date_range(prefs.cluster_time_window_start, prefs.cluster_time_window_end)
    return IngestSettings(
        cluster_similarity_threshold=prefs.cluster_similarity_threshold,
        cluster_time_window_days=prefs.cluster_time_window_days,
        start_date=prefs.cluster_time_window_start,
        end_date=prefs.cluster_time_window_end,
    )


@router.post("/admin/ingest", response_model=IngestionJobStartResponse)
def ingest(payload: IngestRequest | None = None, db: Session = Depends(get_db)):
    prefs = ensure_preferences(db)
    threshold = (
        payload.cluster_similarity_threshold
        if payload and payload.cluster_similarity_threshold is not None
        else prefs.cluster_similarity_threshold
    )

    prefs.cluster_similarity_threshold = threshold
    if payload and (payload.start_date is not None or payload.end_date is not None):
        if payload.start_date is None or payload.end_date is None:
            raise HTTPException(status_code=422, detail="Both start_date and end_date are required.")
        _validate_date_range(payload.start_date, payload.end_date)
        start_date, end_date = payload.start_date, payload.end_date
        start_datetime, end_datetime = _normalize_range_to_utc_bounds(start_date, end_date)
    elif payload and payload.cluster_time_window_days is not None:
        # Backward-compatible semantics for legacy day-based callers:
        # preserve rolling "last N days up to now" clustering bounds.
        start_datetime, end_datetime = _rolling_window_bounds(payload.cluster_time_window_days)
        # Persist a date range for settings UI/API without changing the rolling runtime behavior.
        start_date, end_date = _default_date_range(payload.cluster_time_window_days)
    else:
        start_date, end_date = prefs.cluster_time_window_start, prefs.cluster_time_window_end
        _validate_date_range(start_date, end_date)
        start_datetime, end_datetime = _normalize_range_to_utc_bounds(start_date, end_date)

    prefs.cluster_time_window_start = start_date
    prefs.cluster_time_window_end = end_date
    prefs.cluster_time_window_days = _window_days_from_range(start_date, end_date)
    db.commit()

    with _ingest_lock:
        running_job = _get_running_job(db)
        if running_job:
            recovered = _recover_orphaned_running_job(db, running_job)
            if not recovered:
                return IngestionJobStartResponse(job_id=str(running_job.id), status="RUNNING", already_running=True)

        now = datetime.now(timezone.utc)
        job = IngestionJob(
            id=uuid4(),
            status="RUNNING",
            total_items=0,
            processed_items=0,
            progress_percent=0,
            started_at=now,
            updated_at=now,
        )
        db.add(job)
        db.commit()
    try:
        Thread(
            target=run_ingestion_job,
            args=(job.id, threshold, start_datetime, end_datetime),
            daemon=True,
        ).start()
    except Exception as exc:
        failed_job = db.get(IngestionJob, job.id)
        if failed_job:
            failed_job.status = "FAILED"
            failed_job.updated_at = datetime.now(timezone.utc)
            db.commit()
        raise HTTPException(status_code=500, detail="Failed to start ingestion worker") from exc

    return IngestionJobStartResponse(job_id=str(job.id), status="RUNNING", already_running=False)


@router.get("/admin/ingest/status/current", response_model=IngestionJobStatus | None)
def ingest_status_current(db: Session = Depends(get_db)):
    job = _get_running_job(db)
    job = _recover_if_stale_running_job(db, job)
    if not job:
        return None
    return _as_status(job)


@router.get("/admin/ingest/status/latest", response_model=IngestionJobStatus | None)
def ingest_status_latest(db: Session = Depends(get_db)):
    job = _get_latest_job(db)
    if not job:
        return None

    if job.status == "RUNNING":
        recovered_job = _recover_if_stale_running_job(db, job)
        if recovered_job is None:
            job = _get_latest_job(db)
            if not job:
                return None
        else:
            job = recovered_job

    return _as_status(job)


@router.get("/admin/ingest/status/{job_id}", response_model=IngestionJobStatus)
def ingest_status(job_id: str, db: Session = Depends(get_db)):
    try:
        parsed_id = UUID(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Ingestion job not found") from exc

    job = db.get(IngestionJob, parsed_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")

    recovered_job = _recover_if_stale_running_job(db, job)
    if recovered_job is None:
        job = db.get(IngestionJob, parsed_id)
        if not job:
            raise HTTPException(status_code=404, detail="Ingestion job not found")
    else:
        job = recovered_job

    return _as_status(job)


@router.get("/api/ingestion/status")
def api_ingestion_status(db: Session = Depends(get_db)):
    job = db.query(IngestionJob).order_by(IngestionJob.started_at.desc()).first()
    if job and job.status == "RUNNING":
        recovered_job = _recover_if_stale_running_job(db, job)
        if recovered_job is None:
            job = db.query(IngestionJob).order_by(IngestionJob.started_at.desc()).first()
        else:
            job = recovered_job

    if not job:
        return {
            "status": "COMPLETED",
            "total_items": 0,
            "processed_items": 0,
            "progress_percent": 100,
            "eta_seconds": None,
            "phase": INGESTION_PHASES[-1],
        }

    return {
        "status": job.status,
        "total_items": job.total_items,
        "processed_items": job.processed_items,
        "progress_percent": job.progress_percent,
        "eta_seconds": None,
        "phase": _derive_phase(job),
    }
