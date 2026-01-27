from datetime import datetime, timedelta, timezone
from rapidfuzz import fuzz
from sqlalchemy.orm import Session
from app.models.article import Article
from app.models.cluster import Cluster
from app.services.ingest.normalize import normalize_title

def cluster_recent(db: Session, hours: int = 48) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = (
        db.query(Article)
        .filter(Article.published_at != None)
        .filter(Article.published_at >= cutoff)
        .order_by(Article.published_at.desc())
        .all()
    )

    # Clear cluster_id for window articles (MVP: re-cluster each run)
    for a in articles:
        a.cluster_id = None
    db.flush()

    existing_clusters: list[tuple[int, str]] = []  # (cluster_id, rep_title_norm)
    cluster_members: dict[int, list[Article]] = {}

    threshold = 88  # tune later

    for a in articles:
        tnorm = normalize_title(a.title)
        assigned = None
        for cid, rep in existing_clusters:
            if fuzz.token_set_ratio(tnorm, rep) >= threshold:
                assigned = cid
                break
        if assigned is None:
            c = Cluster(cluster_title=a.title)
            db.add(c)
            db.flush()
            existing_clusters.append((c.id, tnorm))
            assigned = c.id
        cluster_members.setdefault(assigned, []).append(a)
        a.cluster_id = assigned

    # Update stats
    for cid, members in cluster_members.items():
        sources = {m.source_id for m in members}
        latest = max([m.published_at for m in members if m.published_at], default=None)
        c = db.query(Cluster).get(cid)
        c.coverage_count = len(sources)
        c.latest_published_at = latest

    db.commit()
