from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.core.db import get_db
from app.models.cluster import Cluster
from app.models.article import Article
from app.schemas.common import ActionRequest
from app.schemas.cluster import ClusterOut, ClusterArticle
from app.services.workflow.transitions import apply_action

router = APIRouter(prefix="/queue", tags=["queue"])

def cluster_payload(db: Session, c: Cluster) -> ClusterOut:
    members = (
        db.query(Article)
        .filter(Article.cluster_id == c.id)
        .order_by(Article.published_at.desc().nullslast())
        .all()
    )
    coverage = []
    for a in members[:15]:
        coverage.append(ClusterArticle(
            id=a.id,
            title=a.title,
            url=a.url,
            source_name=a.source.name if a.source else "Unknown",
            published_at=a.published_at,
        ))
    canonical = coverage[0] if coverage else None

    why = f"Covered by {c.coverage_count} outlets"
    if c.latest_published_at:
        why += f"; latest {c.latest_published_at.isoformat()}"

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

@router.post("/cluster/{cluster_id}/action")
def act_on_cluster(cluster_id: int, payload: ActionRequest, db: Session = Depends(get_db)):
    members = db.query(Article).filter(Article.cluster_id == cluster_id).all()
    for a in members:
        if a.status == "INBOX":
            a.status = apply_action(a.status, payload.action)
    db.commit()
    return {"ok": True}
