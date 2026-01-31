from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.core.db import get_db
from app.models.article import Article
from app.models.cluster import Cluster
from app.models.summary import Summary
from app.models.profile import Profile
from app.schemas.cluster import ClusterOut, ClusterArticle
from app.services.workflow.transitions import mark_published
from app.services.ingest.extract_content import extract_article_text
from app.services.ai.summarizer import generate_summary
from app.core.config import settings

router = APIRouter(prefix="/shortlist", tags=["shortlist"])

def cluster_out(db: Session, c: Cluster) -> ClusterOut:
    members = (
        db.query(Article)
        .filter(Article.cluster_id == c.id)
        .order_by(Article.published_at.desc().nullslast())
        .all()
    )
    coverage = [
        ClusterArticle(
            id=a.id,
            title=a.title,
            url=a.url,
            source_name=a.source.name if a.source else "Unknown",
            published_at=a.published_at,
        )
        for a in members[:15]
    ]
    canonical = coverage[0] if coverage else None
    why = "Shortlisted story"
    return ClusterOut(
        id=c.id,
        cluster_title=c.cluster_title,
        coverage_count=c.coverage_count,
        latest_published_at=c.latest_published_at,
        score=c.score,
        why=why,
        canonical=canonical,
        coverage=coverage,
    )

@router.get("", response_model=list[ClusterOut])
def list_shortlist(db: Session = Depends(get_db)):
    clusters = (
        db.query(Cluster)
        .join(Article, Article.cluster_id == Cluster.id)
        .filter(Article.status == "SHORTLIST")
        .order_by(desc(Cluster.latest_published_at))
        .all()
    )
    seen, out = set(), []
    for c in clusters:
        if c.id in seen:
            continue
        seen.add(c.id)
        out.append(cluster_out(db, c))
    return out

@router.post("/cluster/{cluster_id}/generate-summary")
def gen_summary(cluster_id: int, db: Session = Depends(get_db)):
    c = db.query(Cluster).get(cluster_id)
    if not c:
        raise HTTPException(404, "Cluster not found")

    profile = db.query(Profile).order_by(Profile.id.asc()).first()
    if not profile:
        raise HTTPException(500, "Profile missing")

    canonical = (
        db.query(Article)
        .filter(Article.cluster_id == cluster_id)
        .order_by(Article.published_at.desc().nullslast())
        .first()
    )
    if not canonical:
        raise HTTPException(400, "No canonical article")

    content = canonical.content_text
    if not content:
        content = extract_article_text(canonical.url)
        canonical.content_text = content
        db.commit()

    if not content:
        content = canonical.raw_excerpt or canonical.title

    if not settings.openai_api_key:
        raise HTTPException(503, "OpenAI API key missing")

    try:
        text = generate_summary(
            audience=profile.audience_text,
            tone=profile.tone_text,
            title=canonical.title,
            url=canonical.url,
            content=(content or "")[:12000],
        )
    except Exception as exc:
        raise HTTPException(502, f"Summary generation failed: {exc}") from exc

    s = db.query(Summary).filter(Summary.cluster_id == cluster_id).first()
    if not s:
        s = Summary(cluster_id=cluster_id, draft_text=text)
        db.add(s)
    else:
        s.draft_text = text
    db.commit()
    return {"ok": True}

@router.post("/cluster/{cluster_id}/publish")
def publish(cluster_id: int, db: Session = Depends(get_db)):
    members = db.query(Article).filter(Article.cluster_id == cluster_id).all()
    changed = 0
    for a in members:
        if a.status == "SHORTLIST":
            a.status = mark_published(a.status)
            changed += 1
    db.commit()
    return {"ok": True, "changed": changed}
