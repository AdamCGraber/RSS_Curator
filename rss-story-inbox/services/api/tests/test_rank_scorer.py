import unittest

from app.services.rank.relevance import cluster_relevance_from_articles


class RankScorerTests(unittest.TestCase):
    def test_cluster_relevance_prefers_multiple_good_articles(self):
        one_strong = cluster_relevance_from_articles([0.9, 0.0, 0.0])
        many_relevant = cluster_relevance_from_articles([0.6, 0.6, 0.6])
        self.assertGreater(many_relevant, one_strong)

    def test_cluster_relevance_penalizes_negative_articles(self):
        mostly_positive = cluster_relevance_from_articles([0.7, 0.5])
        with_negative = cluster_relevance_from_articles([0.7, -0.6, -0.4])
        self.assertLess(with_negative, mostly_positive)


if __name__ == "__main__":
    unittest.main()
