from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from app.core.db import get_db
from app.models.cluster import Cluster
from app.models.article import Article
from app.models.profile import Profile
from app.schemas.common import ActionRequest
from app.schemas.cluster import ClusterOut, ClusterArticle
from app.services.workflow.transitions import apply_action
from app.services.cluster.clusterer import similarity_score
from app.services.filtering.terms import find_matching_terms, parse_terms

router = APIRouter(prefix="/queue", tags=["queue"])


class UndoRequest(BaseModel):
    article_ids: list[int]


def _article_payload(a: Article, canonical_member: Article | None) -> ClusterArticle:
    confidence = similarity_score(canonical_member.title, a.title) if canonical_member else None
    return ClusterArticle(
        id=a.id,
        title=a.title,
        url=a.url,
        source_name=a.source.name if a.source else "Unknown",
        published_at=a.published_at,
        match_confidence=confidence,
    )


def cluster_payload(db: Session, c: Cluster) -> ClusterOut:
    members = (
        db.query(Article)
        .filter(Article.cluster_id == c.id)
        .order_by(Article.published_at.desc().nullslast())
        .all()
    )

    canonical_member = next((m for m in members if m.id == c.canonical_article_id), members[0] if members else None)

    coverage_members = members[:15]
    if canonical_member and all(m.id != canonical_member.id for m in coverage_members):
        coverage_members = [canonical_member, *coverage_members[:14]]

    coverage = [_article_payload(a, canonical_member) for a in coverage_members]

    canonical = _article_payload(canonical_member, canonical_member) if canonical_member else (coverage[0] if coverage else None)

    why = f"Covered by {c.coverage_count} outlets"
    if c.latest_published_at:
        why += f"; latest {c.latest_published_at.isoformat()}"

    profile = db.query(Profile).order_by(Profile.id.asc()).first()
    include_terms = parse_terms(profile.include_terms if profile else None)
    qualifying_terms = find_matching_terms(
        [
            text
            for m in members
            for text in (m.title, m.raw_excerpt, m.content_text)
        ],
        include_terms,
    )

    return ClusterOut(
        id=c.id,
        cluster_title=c.cluster_title,
        coverage_count=c.coverage_count,
        latest_published_at=c.latest_published_at,
        score=c.score,
        why=why,
        qualifying_terms=qualifying_terms,
        canonical=canonical,
        coverage=coverage,
    )


@router.get("/next", response_model=ClusterOut | None)
def next_cluster(db: Session = Depends(get_db)):
    c = (
        db.query(Cluster)
        .join(Article, Article.cluster_id == Cluster.id)
        .filter(Article.status == "INBOX")
        .order_by(desc(Cluster.score), desc(Cluster.latest_published_at))
        .first()
    )
    if not c:
        return None
    return cluster_payload(db, c)


@router.get("/count")
def queue_count(db: Session = Depends(get_db)):
    qualified_cluster_count = (
        db.query(func.count(func.distinct(Article.cluster_id)))
        .filter(Article.status == "INBOX")
        .scalar()
    ) or 0
    return {"articles_to_review": qualified_cluster_count}


@router.post("/cluster/{cluster_id}/action")
def act_on_cluster(cluster_id: int, payload: ActionRequest, db: Session = Depends(get_db)):
    members = db.query(Article).filter(Article.cluster_id == cluster_id).all()
    affected_article_ids: list[int] = []
    for a in members:
        if a.status == "INBOX":
            a.status = apply_action(a.status, payload.action)
            affected_article_ids.append(a.id)
    db.commit()
    return {"ok": True, "affected_article_ids": affected_article_ids}


@router.post("/cluster/{cluster_id}/undo")
def undo_cluster_action(cluster_id: int, payload: UndoRequest, db: Session = Depends(get_db)):
    if not payload.article_ids:
        raise HTTPException(status_code=400, detail="No article ids provided for undo")

    members = (
        db.query(Article)
        .filter(
            Article.cluster_id == cluster_id,
            Article.id.in_(payload.article_ids),
        )
        .all()
    )
    if not members:
        raise HTTPException(status_code=404, detail="No matching cluster articles found for undo")

    reverted_count = 0
    for a in members:
        if a.status in {"KEPT", "REJECTED"}:
            a.status = "INBOX"
            reverted_count += 1

    if reverted_count == 0:
        raise HTTPException(status_code=409, detail="No reversible queue action found for cluster")

    db.commit()
    return {"ok": True, "reverted_items": reverted_count}
