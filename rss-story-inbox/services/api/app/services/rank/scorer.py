from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.cluster import Cluster
from app.models.profile import Profile

def score_clusters(db: Session) -> None:
    profile = db.query(Profile).order_by(Profile.id.asc()).first()
    include_terms = (profile.include_terms or "").lower().split(",") if profile else []
    include_terms = [t.strip() for t in include_terms if t.strip()]

    now = datetime.now(timezone.utc)

    clusters = db.query(Cluster).all()
    for c in clusters:
        coverage = float(c.coverage_count or 1)
        recency_boost = 0.0
        if c.latest_published_at:
            age_hours = (now - c.latest_published_at).total_seconds() / 3600.0
            recency_boost = max(0.0, 48.0 - age_hours) / 48.0

        term_boost = 0.0
        if include_terms:
            title_l = (c.cluster_title or "").lower()
            hits = sum(1 for t in include_terms if t in title_l)
            term_boost = min(1.0, hits * 0.25)

        c.score = (coverage * 10.0) + (recency_boost * 5.0) + (term_boost * 2.0)

    db.commit()
