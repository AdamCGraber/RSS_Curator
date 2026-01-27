from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.core.db import get_db
from app.models.article import Article
from app.models.cluster import Cluster
from app.schemas.cluster import ClusterOut, ClusterArticle
from app.services.workflow.transitions import promote_to_shortlist

router = APIRouter(prefix="/kept", tags=["kept"])

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
    why = f"Kept story; covered by {c.coverage_count} outlets"
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
def list_kept(db: Session = Depends(get_db)):
    clusters = (
        db.query(Cluster)
        .join(Article, Article.cluster_id == Cluster.id)
        .filter(Article.status == "KEPT")
        .order_by(desc(Cluster.latest_published_at))
        .all()
    )
    seen = set()
    out = []
    for c in clusters:
        if c.id in seen:
            continue
        seen.add(c.id)
        out.append(cluster_out(db, c))
    return out

@router.post("/cluster/{cluster_id}/promote")
def promote_cluster(cluster_id: int, db: Session = Depends(get_db)):
    members = db.query(Article).filter(Article.cluster_id == cluster_id).all()
    changed = 0
    for a in members:
        if a.status == "KEPT":
            a.status = promote_to_shortlist(a.status)
            changed += 1
    db.commit()
    return {"ok": True, "changed": changed}
