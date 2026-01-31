from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from app.core.db import get_db
from app.models.source import Source
from app.models.article import Article
from app.core.config import settings
from app.services.ingest.fetch_rss import fetch_feed
from app.services.cluster.clusterer import cluster_recent
from app.services.rank.scorer import score_clusters

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/ingest")
def ingest(db: Session = Depends(get_db)):
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

    cluster_recent(db, hours=settings.cluster_time_window_hours)
    score_clusters(db)

    return {"inserted": inserted, "skipped": attempted - inserted}
