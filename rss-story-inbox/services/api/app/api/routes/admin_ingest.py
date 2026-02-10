from datetime import datetime, timezone
from threading import Lock, Thread
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from app.core.db import SessionLocal, get_db
from app.models.article import Article
from app.models.user_preference import UserPreference
from app.core.config import settings
from app.services.ingest.fetch_rss import fetch_feed
from app.services.cluster.clusterer import cluster_recent
from app.services.rank.scorer import score_clusters
from app.services.sources_state import get_active_sources_snapshot

router = APIRouter(prefix="/admin", tags=["admin"])


class IngestionJobStatus(BaseModel):
    job_id: str
    status: str
    started_at: str
    completed_at: str | None = None
    inserted: int | None = None
    skipped: int | None = None
    cluster_similarity_threshold: float | None = None
    cluster_time_window_days: int | None = None
    error: str | None = None
    message: str | None = None


class IngestionJobStartResponse(BaseModel):
    job_id: str
    status: str
    already_running: bool = False


class IngestionJobStore:
    def __init__(self):
        self._lock = Lock()
        self._current_job_id: str | None = None
        self._jobs: dict[str, dict] = {}

    def start_job(self, threshold: float, window_days: int) -> tuple[str, bool]:
        with self._lock:
            if self._current_job_id:
                current_job = self._jobs.get(self._current_job_id)
                if current_job and current_job["status"] == "running":
                    return self._current_job_id, True

            job_id = str(uuid4())
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": None,
                "inserted": None,
                "skipped": None,
                "cluster_similarity_threshold": threshold,
                "cluster_time_window_days": window_days,
                "error": None,
                "message": None,
            }
            self._current_job_id = job_id
            return job_id, False

    def get_job(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def get_current_running_job(self) -> dict | None:
        with self._lock:
            if not self._current_job_id:
                return None
            job = self._jobs.get(self._current_job_id)
            if not job or job["status"] != "running":
                return None
            return dict(job)

    def finish_job(self, job_id: str, status: str, **updates):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.update(
                {
                    "status": status,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    **updates,
                }
            )
            if self._current_job_id == job_id:
                self._current_job_id = None


job_store = IngestionJobStore()


class IngestSettings(BaseModel):
    cluster_similarity_threshold: float = Field(0.88, ge=0.0, le=1.0)
    cluster_time_window_days: int = Field(2, ge=1, le=30)


class IngestRequest(BaseModel):
    cluster_similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    cluster_time_window_days: int | None = Field(default=None, ge=1, le=30)


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


def run_ingestion_job(job_id: str, threshold: float, window_days: int):
    db = SessionLocal()
    try:
        snapshot = get_active_sources_snapshot(db)
        sources = snapshot.get("sources", [])
        inserted = 0
        attempted = 0

        for s in sources:
            items = fetch_feed(s["feed_url"])
            rows = []
            for it in items:
                url = it.get("url")
                if not url:
                    continue
                rows.append(
                    {
                        "source_id": s["id"],
                        "url": url,
                        "title": (it.get("title") or "")[:512],
                        "raw_excerpt": it.get("summary") or None,
                        "published_at": it.get("published_at"),
                        "status": "INBOX",
                    }
                )
            if not rows:
                continue
            attempted += len(rows)
            stmt = insert(Article).values(rows).on_conflict_do_nothing(index_elements=["url"])
            result = db.execute(stmt)
            inserted += result.rowcount or 0

        db.commit()
        cluster_recent(db, threshold=threshold, time_window_days=window_days)
        score_clusters(db)
        db.commit()

        job_store.finish_job(
            job_id,
            "completed",
            inserted=inserted,
            skipped=attempted - inserted,
            cluster_similarity_threshold=threshold,
            cluster_time_window_days=window_days,
            message="Ingestion complete.",
        )
    except IntegrityError:
        db.rollback()
        job_store.finish_job(
            job_id,
            "failed",
            error="Integrity error while ingesting articles. Please retry after resolving duplicates.",
            message="Ingestion failed.",
        )
    except Exception as exc:
        db.rollback()
        job_store.finish_job(
            job_id,
            "failed",
            error=str(exc),
            message="Ingestion failed.",
        )
    finally:
        db.close()


@router.get("/ingest/settings", response_model=IngestSettings)
def ingest_settings(db: Session = Depends(get_db)):
    prefs = ensure_preferences(db)
    return IngestSettings(
        cluster_similarity_threshold=prefs.cluster_similarity_threshold,
        cluster_time_window_days=prefs.cluster_time_window_days,
    )


@router.post("/ingest")
def ingest(payload: IngestRequest | None = None, db: Session = Depends(get_db)):
    prefs = ensure_preferences(db)
    threshold = payload.cluster_similarity_threshold if payload and payload.cluster_similarity_threshold is not None else prefs.cluster_similarity_threshold
    window_days = payload.cluster_time_window_days if payload and payload.cluster_time_window_days is not None else prefs.cluster_time_window_days

    prefs.cluster_similarity_threshold = threshold
    prefs.cluster_time_window_days = window_days
    db.commit()

    job_id, already_running = job_store.start_job(threshold=threshold, window_days=window_days)
    if not already_running:
        Thread(target=run_ingestion_job, args=(job_id, threshold, window_days), daemon=True).start()
    return IngestionJobStartResponse(job_id=job_id, status="running", already_running=already_running)


@router.get("/ingest/status/current", response_model=IngestionJobStatus | None)
def ingest_status_current():
    job = job_store.get_current_running_job()
    if not job:
        return None
    return IngestionJobStatus(**job)


@router.get("/ingest/status/{job_id}", response_model=IngestionJobStatus)
def ingest_status(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return IngestionJobStatus(**job)
