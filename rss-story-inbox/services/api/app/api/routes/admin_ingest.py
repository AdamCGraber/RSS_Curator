from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from app.core.db import get_db
from app.models.source import Source
from app.models.article import Article
from app.models.user_preference import UserPreference
from app.core.config import settings
from app.services.ingest.fetch_rss import fetch_feed
from app.services.cluster.clusterer import cluster_recent
from app.services.rank.scorer import score_clusters

router = APIRouter(prefix="/admin", tags=["admin"])


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

    sources = db.query(Source).filter(Source.active == True).all()
    inserted = 0
    attempted = 0

    try:
        for s in sources:
            items = fetch_feed(s.feed_url)
            rows = []
            for it in items:
                url = it.get("url")
                if not url:
                    continue
                rows.append(
                    {
                        "source_id": s.id,
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
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Integrity error while ingesting articles. Please retry after resolving duplicates.",
        )

    cluster_recent(db, threshold=threshold, time_window_days=window_days)
    score_clusters(db)

    return {
        "inserted": inserted,
        "skipped": attempted - inserted,
        "cluster_similarity_threshold": threshold,
        "cluster_time_window_days": window_days,
    }
