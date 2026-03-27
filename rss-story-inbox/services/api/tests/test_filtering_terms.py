import unittest

from app.services.filtering.terms import (
    find_matching_terms,
    parse_terms,
    score_article_relevance,
    should_keep_article,
)


class FilteringTermsTests(unittest.TestCase):
    def test_parse_terms_normalizes(self):
        self.assertEqual(parse_terms(" AI,  Space  ,"), ["ai", "space"])

    def test_include_match_kept(self):
        self.assertTrue(
            should_keep_article(
                title="AI regulation update",
                excerpt="",
                include_terms=["ai"],
                exclude_terms=["sports"],
            )
        )

    def test_exclude_match_dropped_without_include_terms(self):
        self.assertFalse(
            should_keep_article(
                title="Sports roundup",
                excerpt="",
                include_terms=[],
                exclude_terms=["sports"],
            )
        )

    def test_include_overrides_exclude(self):
        self.assertTrue(
            should_keep_article(
                title="AI in sports analytics",
                excerpt="",
                include_terms=["ai"],
                exclude_terms=["sports"],
            )
        )

    def test_include_terms_restrict_when_configured(self):
        self.assertFalse(
            should_keep_article(
                title="Markets today",
                excerpt="",
                include_terms=["ai"],
                exclude_terms=[],
            )
        )

    def test_article_relevance_weights_title_more_than_excerpt(self):
        title_score = score_article_relevance(
            title="AI policy update",
            excerpt="",
            content="",
            include_terms=["ai"],
            exclude_terms=[],
        )
        excerpt_score = score_article_relevance(
            title="",
            excerpt="AI policy update",
            content="",
            include_terms=["ai"],
            exclude_terms=[],
        )
        self.assertGreater(title_score, excerpt_score)

    def test_article_relevance_applies_exclude_penalty(self):
        score = score_article_relevance(
            title="AI policy update",
            excerpt="sports conflict",
            content="",
            include_terms=["ai"],
            exclude_terms=["sports"],
        )
        self.assertLess(score, 0.5)

    def test_find_matching_terms_returns_include_terms_present_in_text(self):
        matched = find_matching_terms(
            texts=["AI policy update", "Markets and Space startups"],
            terms=["ai", "space", "healthcare"],
        )
        self.assertEqual(matched, ["ai", "space"])

    def test_find_matching_terms_deduplicates_and_normalizes(self):
        matched = find_matching_terms(
            texts=["Policy updates on AI safety and governance"],
            terms=["AI", " ai ", "safety"],
        )
        self.assertEqual(matched, ["ai", "safety"])


if __name__ == "__main__":
    unittest.main()
