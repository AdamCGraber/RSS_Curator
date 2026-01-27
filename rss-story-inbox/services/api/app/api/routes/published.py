from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.core.db import get_db
from app.models.cluster import Cluster
from app.models.article import Article
from app.models.summary import Summary

router = APIRouter(prefix="/published", tags=["published"])

@router.get("")
def list_published(db: Session = Depends(get_db)):
    clusters = (
        db.query(Cluster)
        .join(Article, Article.cluster_id == Cluster.id)
        .filter(Article.status == "PUBLISHED")
        .order_by(desc(Cluster.latest_published_at))
        .all()
    )
    seen = set()
    out = []
    for c in clusters:
        if c.id in seen:
            continue
        seen.add(c.id)
        s = db.query(Summary).filter(Summary.cluster_id == c.id).first()
        out.append({
            "cluster_id": c.id,
            "title": c.cluster_title,
            "coverage_count": c.coverage_count,
            "latest_published_at": c.latest_published_at.isoformat() if c.latest_published_at else None,
            "summary": (s.edited_text or s.draft_text) if s else None
        })
    return out
