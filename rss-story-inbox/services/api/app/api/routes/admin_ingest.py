from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
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
    created = 0

    for s in sources:
        items = fetch_feed(s.feed_url)
        for it in items:
            existing = db.query(Article).filter(Article.url == it["url"]).first()
            if existing:
                continue
            a = Article(
                source_id=s.id,
                url=it["url"],
                title=(it["title"] or "")[:512],
                raw_excerpt=(it.get("summary") or None),
                published_at=it.get("published_at"),
                status="INBOX",
            )
            db.add(a)
            created += 1

    db.commit()

    cluster_recent(db, hours=settings.cluster_time_window_hours)
    score_clusters(db)

    return {"ok": True, "sources": len(sources), "new_articles": created}
