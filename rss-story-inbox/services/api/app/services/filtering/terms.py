from __future__ import annotations

TITLE_WEIGHT = 3.0
SUMMARY_WEIGHT = 2.0
CONTENT_WEIGHT = 1.0


def parse_terms(raw_terms: str | None) -> list[str]:
    if not raw_terms:
        return []

    return [term.strip().lower() for term in raw_terms.split(",") if term.strip()]


def find_matching_terms(texts: list[str | None], terms: list[str]) -> list[str]:
    if not texts or not terms:
        return []

    searchable = " ".join(text for text in texts if text).lower()
    if not searchable:
        return []

    seen: set[str] = set()
    matched: list[str] = []
    for term in terms:
        normalized = term.strip().lower()
        if not normalized or normalized in seen:
            continue
        if normalized in searchable:
            matched.append(normalized)
            seen.add(normalized)

    return matched


def _weighted_hits(text: str, terms: list[str], weight: float) -> float:
    if not text or not terms:
        return 0.0

    lowered = text.lower()
    return float(sum(weight for term in terms if term in lowered))


def score_article_relevance(
    title: str | None,
    excerpt: str | None,
    content: str | None,
    include_terms: list[str],
    include_terms_2: list[str],
    exclude_terms: list[str],
) -> float:
    """Score article relevance using weighted include/exclude term matching.

    Field weights:
    - title: strong
    - excerpt/summary: medium
    - content/body: light

    Output is approximately in range [-1.0, 1.0]. Positive means relevant.
    """

    all_include_terms = [*include_terms, *include_terms_2]

    include_raw = (
        _weighted_hits(title or "", all_include_terms, TITLE_WEIGHT)
        + _weighted_hits(excerpt or "", all_include_terms, SUMMARY_WEIGHT)
        + _weighted_hits(content or "", all_include_terms, CONTENT_WEIGHT)
    )
    exclude_raw = (
        _weighted_hits(title or "", exclude_terms, TITLE_WEIGHT)
        + _weighted_hits(excerpt or "", exclude_terms, SUMMARY_WEIGHT)
        + _weighted_hits(content or "", exclude_terms, CONTENT_WEIGHT)
    )

    max_field_weight = TITLE_WEIGHT + SUMMARY_WEIGHT + CONTENT_WEIGHT
    include_norm = include_raw / (len(all_include_terms) * max_field_weight) if all_include_terms else 0.0
    exclude_norm = exclude_raw / (len(exclude_terms) * max_field_weight) if exclude_terms else 0.0

    return include_norm - exclude_norm


def should_keep_article(
    title: str | None,
    excerpt: str | None,
    include_terms: list[str],
    include_terms_2: list[str],
    exclude_terms: list[str],
) -> bool:
    """Return True when an article should remain in INBOX.

    Rules:
    - If include terms are configured, article is kept only when include matching rules pass.
    - When both include lists are configured, one term from each list must match.
    - When only the first include list is configured, any term from it may match.
    - The second include list never qualifies an article by itself.
    - Exclude terms remove articles unless there is an include match.
    - Include matches always override exclude matches.
    """

    searchable = f"{title or ''} {excerpt or ''}".lower()

    include_hit = any(term in searchable for term in include_terms)
    include_hit_2 = any(term in searchable for term in include_terms_2)
    exclude_hit = any(term in searchable for term in exclude_terms)

    if include_terms and include_terms_2:
        return include_hit and include_hit_2

    if include_terms:
        return include_hit

    if include_terms_2:
        return False

    if exclude_hit:
        return False

    return True
