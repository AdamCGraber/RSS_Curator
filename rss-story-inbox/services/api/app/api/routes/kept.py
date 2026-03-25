from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.article import Article
from app.models.cluster import Cluster
from app.schemas.cluster import ClusterArticle, ClusterOut
from app.services.workflow.transitions import promote_to_shortlist, remove_from_kept

router = APIRouter(prefix="/kept", tags=["kept"])


def _article_payload(a: Article) -> ClusterArticle:
    return ClusterArticle(
        id=a.id,
        title=a.title,
        url=a.url,
        source_name=a.source.name if a.source else "Unknown",
        published_at=a.published_at,
    )


def cluster_out(db: Session, c: Cluster) -> ClusterOut:
    members = (
        db.query(Article)
        .filter(Article.cluster_id == c.id)
        .order_by(Article.published_at.desc().nullslast())
        .all()
    )

    canonical_member = next(
        (m for m in members if m.id == c.canonical_article_id),
        members[0] if members else None,
    )

    coverage_members = members[:15]
    if canonical_member and all(m.id != canonical_member.id for m in coverage_members):
        coverage_members = [canonical_member, *coverage_members[:14]]

    coverage = [_article_payload(a) for a in coverage_members]
    canonical = _article_payload(canonical_member) if canonical_member else (coverage[0] if coverage else None)

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
        .order_by(desc(Cluster.score), desc(Cluster.latest_published_at), desc(Cluster.id))
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


@router.post("/cluster/{cluster_id}/remove")
def remove_cluster(cluster_id: int, db: Session = Depends(get_db)):
    members = db.query(Article).filter(Article.cluster_id == cluster_id).all()
    changed = 0
    for a in members:
        if a.status == "KEPT":
            a.status = remove_from_kept(a.status)
            changed += 1
    db.commit()
    return {"ok": True, "changed": changed}
