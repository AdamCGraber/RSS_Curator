from datetime import datetime, timezone
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
    cluster_time_window_days: int = Field(2, ge=1, le=30)


class IngestRequest(BaseModel):
    cluster_similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    cluster_time_window_days: int | None = Field(default=None, ge=1, le=30)


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


def ensure_preferences(db: Session) -> UserPreference:
    default_window_days = max(1, int(settings.cluster_time_window_hours / 24) or 2)

    stmt = (
        insert(UserPreference)
        .values(
            user_id=1,
            cluster_similarity_threshold=0.88,
            cluster_time_window_days=default_window_days,
        )
        .on_conflict_do_nothing(index_elements=["user_id"])
    )
    db.execute(stmt)
    db.commit()

    prefs = db.query(UserPreference).filter(UserPreference.user_id == 1).first()
    if not prefs:
        raise HTTPException(status_code=500, detail="Failed to initialize ingest preferences")
    return prefs


def _derive_phase(job: IngestionJob) -> str:
    if job.status == "COMPLETED":
        return INGESTION_PHASES[-1]

    progress = job.progress_percent or 0
    if progress < 20:
        return "DISCOVERING_FEEDS"
    if progress < 40:
        return "IMPORTING_ITEMS"
    if progress < 60:
        return "CLUSTERING"
    if progress < 80:
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
):
    phase_floor = INGESTION_PHASES.index(phase) * 20 if phase in INGESTION_PHASES else 0
    job.processed_items = max(0, processed_items)
    if total_items is not None:
        job.total_items = max(0, total_items)
    job.progress_percent = max(phase_floor, min(100, progress_percent))
    job.updated_at = datetime.now(timezone.utc)
    db.commit()


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


def run_ingestion_job(job_id: UUID, threshold: float, window_days: int):
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
                progress_percent=0,
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
            progress_percent=20,
            processed_items=discovered_feed_count,
        )

        _set_phase_progress(
            db,
            job,
            phase=INGESTION_PHASES[1],
            progress_percent=20,
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
                progress_percent=20,
                processed_items=processed_count,
                total_items=len(discovered_rows),
            )

        _set_phase_progress(
            db,
            job,
            phase=INGESTION_PHASES[1],
            progress_percent=40,
            processed_items=processed_count,
            total_items=len(discovered_rows),
        )

        _set_phase_progress(db, job, phase=INGESTION_PHASES[2], progress_percent=40)
        cluster_recent(db, threshold=threshold, time_window_days=window_days)
        cluster_count = db.query(Article.cluster_id).filter(Article.cluster_id.is_not(None)).distinct().count()
        _set_phase_progress(
            db,
            job,
            phase=INGESTION_PHASES[2],
            progress_percent=60,
            processed_items=cluster_count,
        )

        _set_phase_progress(db, job, phase=INGESTION_PHASES[3], progress_percent=60)
        score_clusters(db)
        scored_clusters = db.query(Article.cluster_id).filter(Article.cluster_id.is_not(None)).distinct().count()
        _set_phase_progress(
            db,
            job,
            phase=INGESTION_PHASES[3],
            progress_percent=80,
            processed_items=scored_clusters,
        )

        _set_phase_progress(db, job, phase=INGESTION_PHASES[4], progress_percent=80)
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
    return IngestSettings(
        cluster_similarity_threshold=prefs.cluster_similarity_threshold,
        cluster_time_window_days=prefs.cluster_time_window_days,
    )


@router.post("/admin/ingest", response_model=IngestionJobStartResponse)
def ingest(payload: IngestRequest | None = None, db: Session = Depends(get_db)):
    prefs = ensure_preferences(db)
    threshold = payload.cluster_similarity_threshold if payload and payload.cluster_similarity_threshold is not None else prefs.cluster_similarity_threshold
    window_days = payload.cluster_time_window_days if payload and payload.cluster_time_window_days is not None else prefs.cluster_time_window_days

    prefs.cluster_similarity_threshold = threshold
    prefs.cluster_time_window_days = window_days
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
        Thread(target=run_ingestion_job, args=(job.id, threshold, window_days), daemon=True).start()
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
