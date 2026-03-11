from __future__ import annotations


def parse_terms(raw_terms: str | None) -> list[str]:
    if not raw_terms:
        return []

    return [term.strip().lower() for term in raw_terms.split(",") if term.strip()]


def should_keep_article(
    title: str | None,
    excerpt: str | None,
    include_terms: list[str],
    exclude_terms: list[str],
) -> bool:
    """Return True when an article should remain in INBOX.

    Rules:
    - If include terms are configured, article is kept only when at least one include term matches.
    - Exclude terms remove articles unless there is an include match.
    - Include matches always override exclude matches.
    """

    searchable = f"{title or ''} {excerpt or ''}".lower()

    include_hit = any(term in searchable for term in include_terms)
    exclude_hit = any(term in searchable for term in exclude_terms)

    if include_terms:
        return include_hit

    if exclude_hit:
        return False

    return True
