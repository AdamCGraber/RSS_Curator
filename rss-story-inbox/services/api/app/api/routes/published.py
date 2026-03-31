from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from urllib.parse import urlparse
from app.core.db import get_db
from app.models.cluster import Cluster
from app.models.article import Article
from app.models.profile import Profile
from app.models.summary import Summary
from app.services.filtering.terms import (
    deserialize_qualifying_terms_snapshot,
    find_cluster_qualifying_terms,
    parse_terms,
)
from app.services.workflow.transitions import remove_from_published

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
    profile = db.query(Profile).order_by(Profile.id.asc()).first()
    include_terms = parse_terms(profile.include_terms if profile else None)
    include_terms_2 = parse_terms(profile.include_terms_2 if profile else None)
    for c in clusters:
        if c.id in seen:
            continue
        seen.add(c.id)
        s = db.query(Summary).filter(Summary.cluster_id == c.id).first()
        published_article = (
            db.query(Article)
            .filter(
                Article.cluster_id == c.id,
                Article.status == "PUBLISHED",
                Article.published_at.isnot(None),
            )
            .order_by(desc(Article.published_at), desc(Article.id))
            .first()
        )
        canonical_url = normalize_http_url(c.canonical_article.url if c.canonical_article else None)
        fallback_url = normalize_http_url(published_article.url if published_article else None)
        qualifying_terms = deserialize_qualifying_terms_snapshot(c.qualifying_terms_snapshot)
        if not qualifying_terms:
            members = db.query(Article).filter(Article.cluster_id == c.id).all()
            qualifying_terms = find_cluster_qualifying_terms(
                [
                    text
                    for m in members
                    for text in (m.title, m.raw_excerpt, m.content_text)
                ],
                include_terms,
                include_terms_2,
            )
        out.append({
            "cluster_id": c.id,
            "title": c.cluster_title,
            "coverage_count": c.coverage_count,
            "latest_published_at": c.latest_published_at.isoformat() if c.latest_published_at else None,
            "summary": (s.edited_text or s.draft_text) if s else None,
            "url": canonical_url or fallback_url,
            "score": c.score,
            "qualifying_terms": qualifying_terms,
        })
    return out


@router.post("/cluster/{cluster_id}/remove")
def remove_cluster(cluster_id: int, db: Session = Depends(get_db)):
    members = db.query(Article).filter(Article.cluster_id == cluster_id).all()
    changed = 0
    for a in members:
        if a.status == "PUBLISHED":
            a.status = remove_from_published(a.status)
            changed += 1
    db.commit()
    return {"ok": True, "changed": changed}
