from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from urllib.parse import urlparse
from app.core.db import get_db
from app.models.cluster import Cluster
from app.models.article import Article
from app.models.summary import Summary

router = APIRouter(prefix="/published", tags=["published"])

def normalize_http_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return value

@router.get("")
def list_published(db: Session = Depends(get_db)):
    clusters = (
        db.query(Cluster)
        .join(Article, Article.cluster_id == Cluster.id)
        .filter(Article.status == "PUBLISHED")
        .order_by(desc(Cluster.score), desc(Cluster.latest_published_at))
        .all()
    )
    seen = set()
    out = []
    for c in clusters:
        if c.id in seen:
            continue
        seen.add(c.id)
        s = db.query(Summary).filter(Summary.cluster_id == c.id).first()
        published_article = (
            db.query(Article)
            .filter(Article.cluster_id == c.id, Article.status == "PUBLISHED")
            .order_by(desc(Article.published_at), desc(Article.id))
            .first()
        )
        canonical_url = normalize_http_url(c.canonical_article.url if c.canonical_article else None)
        fallback_url = normalize_http_url(published_article.url if published_article else None)
        out.append({
            "cluster_id": c.id,
            "title": c.cluster_title,
            "coverage_count": c.coverage_count,
            "latest_published_at": c.latest_published_at.isoformat() if c.latest_published_at else None,
            "summary": (s.edited_text or s.draft_text) if s else None,
            "url": canonical_url or fallback_url,
            "score": c.score,
        })
    return out
