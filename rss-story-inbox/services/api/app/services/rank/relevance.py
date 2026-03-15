TOP_RELEVANT_ARTICLES = 3


def cluster_relevance_from_articles(article_scores: list[float]) -> float:
    if not article_scores:
        return 0.0

    ordered = sorted(article_scores, reverse=True)
    best_score = max(0.0, ordered[0])

    top_positive = [score for score in ordered if score > 0][:TOP_RELEVANT_ARTICLES]
    if top_positive:
        depth_score = sum(top_positive) / 2.0
    else:
        depth_score = 0.0

    top_negative = [-score for score in sorted(article_scores) if score < 0][:TOP_RELEVANT_ARTICLES]
    penalty_score = (sum(top_negative) / 2.0) * 0.5 if top_negative else 0.0

    return best_score + depth_score - penalty_score
