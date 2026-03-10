from datetime import datetime, timezone
from threading import Lock, Thread
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal, get_db
from app.models.article import Article
from app.models.ingestion_job import IngestionJob
from app.models.user_preference import UserPreference
from app.services.cluster.clusterer import cluster_recent
from app.services.ingest.fetch_rss import fetch_feed
from app.services.rank.scorer import score_clusters
from app.services.sources_state import get_active_sources_snapshot

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


def _calculate_eta_seconds(job: IngestionJob) -> int | None:
    if job.processed_items <= 0 or job.total_items <= 0:
        return None

    elapsed = max(0.0, (datetime.now(timezone.utc) - job.started_at).total_seconds())
    if elapsed <= 0:
        return None

    rate = job.processed_items / elapsed
    if rate <= 0:
        return None

    remaining = max(0, job.total_items - job.processed_items)
    if remaining == 0:
        return 0

    return int(round(remaining / rate))


def _as_status(job: IngestionJob) -> IngestionJobStatus:
    return IngestionJobStatus(
        job_id=str(job.id),
        status=job.status,
        started_at=job.started_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        total_items=job.total_items,
        processed_items=job.processed_items,
        progress_percent=job.progress_percent,
        eta_seconds=_calculate_eta_seconds(job),
    )


def _get_running_job(db: Session) -> IngestionJob | None:
    return (
        db.query(IngestionJob)
        .filter(IngestionJob.status == "RUNNING")
        .order_by(IngestionJob.started_at.desc())
        .first()
    )


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

    job.status = "FAILED"
    job.updated_at = now
    db.commit()
    return True


def _update_progress(db: Session, job: IngestionJob, force: bool = False):
    if not force and job.processed_items % 10 != 0:
        return

    if job.total_items <= 0:
        job.progress_percent = 0
    else:
        job.progress_percent = (job.processed_items / job.total_items) * 100
    job.updated_at = datetime.now(timezone.utc)
    db.commit()


def _mark_job_failed(db: Session, job: IngestionJob):
    db.refresh(job)
    job.status = "FAILED"
    job.updated_at = datetime.now(timezone.utc)
    db.commit()


def _mark_job_complete(db: Session, job: IngestionJob):
    db.refresh(job)
    job.processed_items = job.total_items
    job.progress_percent = 100
    job.status = "COMPLETED"
    job.updated_at = datetime.now(timezone.utc)
    db.commit()


def run_ingestion_job(job_id: UUID, threshold: float, window_days: int):
    db = SessionLocal()
    try:
        job = db.get(IngestionJob, job_id)
        if not job:
            return

        snapshot = get_active_sources_snapshot(db)
        sources = snapshot.get("sources", [])

        discovered_rows: list[dict] = []
        for source in sources:
            items = fetch_feed(source["feed_url"])
            for item in items:
                url = item.get("url")
                if not url:
                    continue
                discovered_rows.append(
                    {
                        "source_id": source["id"],
                        "url": url,
                        "title": (item.get("title") or "")[:512],
                        "raw_excerpt": item.get("summary") or None,
                        "published_at": item.get("published_at"),
                        "status": "INBOX",
                    }
                )

        job.total_items = len(discovered_rows)
        job.updated_at = datetime.now(timezone.utc)
        db.commit()

        for row in discovered_rows:
            try:
                stmt = insert(Article).values(row).on_conflict_do_nothing(index_elements=["url"])
                db.execute(stmt)
            except Exception:
                db.rollback()
            finally:
                db.refresh(job)
                job.processed_items += 1
                _update_progress(db, job)

        _update_progress(db, job, force=True)

        cluster_recent(db, threshold=threshold, time_window_days=window_days)
        score_clusters(db)
        db.commit()

        _mark_job_complete(db, job)
    except Exception:
        db.rollback()
        job = db.get(IngestionJob, job_id)
        if job:
            _mark_job_failed(db, job)
    finally:
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

    Thread(target=run_ingestion_job, args=(job.id, threshold, window_days), daemon=True).start()
    return IngestionJobStartResponse(job_id=str(job.id), status="RUNNING", already_running=False)


@router.get("/admin/ingest/status/current", response_model=IngestionJobStatus | None)
def ingest_status_current(db: Session = Depends(get_db)):
    job = _get_running_job(db)
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
    return _as_status(job)


@router.get("/api/ingestion/status")
def api_ingestion_status(db: Session = Depends(get_db)):
    job = db.query(IngestionJob).order_by(IngestionJob.started_at.desc()).first()
    if not job:
        return {
            "status": "COMPLETED",
            "total_items": 0,
            "processed_items": 0,
            "progress_percent": 100,
            "eta_seconds": None,
        }

    return {
        "status": job.status,
        "total_items": job.total_items,
        "processed_items": job.processed_items,
        "progress_percent": job.progress_percent,
        "eta_seconds": _calculate_eta_seconds(job),
    }
