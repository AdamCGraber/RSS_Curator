from datetime import datetime, timedelta, timezone
from rapidfuzz import fuzz
from sqlalchemy.orm import Session
from app.models.article import Article
from app.models.cluster import Cluster
from app.services.ingest.normalize import normalize_title


def similarity_score(left: str, right: str) -> float:
    """Return similarity as 0.0-1.0."""
    a = normalize_title(left)
    b = normalize_title(right)
    token_set = fuzz.token_set_ratio(a, b)
    token_sort = fuzz.token_sort_ratio(a, b)
    return max(token_set, token_sort) / 100.0


def _pick_canonical(members: list[Article]) -> Article:
    if len(members) == 1:
        return members[0]

    best = None
    best_score = -1.0
    for candidate in members:
        others = [m for m in members if m.id != candidate.id]
        if not others:
            avg = 1.0
        else:
            avg = sum(similarity_score(candidate.title, o.title) for o in others) / len(others)

        tie_break_time = candidate.published_at or datetime.max.replace(tzinfo=timezone.utc)
        if avg > best_score:
            best = candidate
            best_score = avg
        elif avg == best_score and best is not None:
            best_time = best.published_at or datetime.max.replace(tzinfo=timezone.utc)
            if tie_break_time < best_time:
                best = candidate

    return best or members[0]


def cluster_recent(db: Session, threshold: float = 0.88, time_window_days: int = 2) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=time_window_days)
    articles = (
        db.query(Article)
        .filter(Article.published_at.isnot(None))
        .filter(Article.published_at >= cutoff)
        .order_by(Article.published_at.desc())
        .all()
    )

    for a in articles:
        a.cluster_id = None
    db.flush()

    existing_clusters: list[tuple[int, str]] = []
    cluster_members: dict[int, list[Article]] = {}

    for a in articles:
        tnorm = normalize_title(a.title)
        assigned = None

        for cid, rep in existing_clusters:
            members = cluster_members.get(cid, [])
            if any(m.source_id == a.source_id for m in members):
                continue
            if similarity_score(tnorm, rep) >= threshold:
                assigned = cid
                break

        if assigned is None:
            c = Cluster(
                cluster_title=a.title,
                created_with_threshold=threshold,
                created_with_time_window_days=time_window_days,
            )
            db.add(c)
            db.flush()
            existing_clusters.append((c.id, tnorm))
            assigned = c.id

        cluster_members.setdefault(assigned, []).append(a)
        a.cluster_id = assigned

    for cid, members in cluster_members.items():
        canonical = _pick_canonical(members)
        scores = [
            similarity_score(canonical.title, member.title) for member in members if member.id != canonical.id
        ]
        avg_similarity = sum(scores) / len(scores) if scores else 1.0

        sources = {m.source_id for m in members}
        latest = max((m.published_at for m in members if m.published_at), default=None)
        c = db.query(Cluster).get(cid)
        c.cluster_title = canonical.title
        c.canonical_article_id = canonical.id
        c.created_with_threshold = threshold
        c.created_with_time_window_days = time_window_days
        c.coverage_count = len(sources)
        c.latest_published_at = latest
        c.score = avg_similarity

    db.commit()
