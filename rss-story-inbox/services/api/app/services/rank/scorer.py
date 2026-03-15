from datetime import datetime, timezone

from sqlalchemy.orm import selectinload

from app.models.cluster import Cluster
from app.models.profile import Profile
from app.services.filtering.terms import parse_terms, score_article_relevance
from app.services.rank.relevance import cluster_relevance_from_articles


def score_clusters(db) -> None:
    profile = db.query(Profile).order_by(Profile.id.asc()).first()
    include_terms = parse_terms(profile.include_terms if profile else None)
    exclude_terms = parse_terms(profile.exclude_terms if profile else None)

    now = datetime.now(timezone.utc)
    has_term_filters = bool(include_terms or exclude_terms)

    clusters_query = db.query(Cluster)
    if has_term_filters:
        clusters_query = clusters_query.options(selectinload(Cluster.articles))
    clusters = clusters_query.all()
    for c in clusters:
        coverage = float(c.coverage_count or 1)
        recency_boost = 0.0
        if c.latest_published_at:
            age_hours = (now - c.latest_published_at).total_seconds() / 3600.0
            recency_boost = max(0.0, 48.0 - age_hours) / 48.0

        relevance_boost = 0.0
        if has_term_filters:
            article_scores = [
                score_article_relevance(
                    title=a.title,
                    excerpt=a.raw_excerpt,
                    content=a.content_text,
                    include_terms=include_terms,
                    exclude_terms=exclude_terms,
                )
                for a in c.articles
            ]
            relevance_boost = cluster_relevance_from_articles(article_scores)

        c.score = (coverage * 10.0) + (recency_boost * 5.0) + (relevance_boost * 4.0)

    db.commit()
