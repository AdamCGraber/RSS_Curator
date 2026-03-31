import unittest

from app.services.filtering.terms import (
    deserialize_qualifying_terms_snapshot,
    find_cluster_qualifying_terms,
    find_matching_terms,
    parse_terms,
    score_article_relevance,
    serialize_qualifying_terms_snapshot,
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
                include_terms_2=[],
                exclude_terms=["sports"],
            )
        )

    def test_exclude_match_dropped_without_include_terms(self):
        self.assertFalse(
            should_keep_article(
                title="Sports roundup",
                excerpt="",
                include_terms=[],
                include_terms_2=[],
                exclude_terms=["sports"],
            )
        )

    def test_include_overrides_exclude(self):
        self.assertTrue(
            should_keep_article(
                title="AI in sports analytics",
                excerpt="",
                include_terms=["ai"],
                include_terms_2=[],
                exclude_terms=["sports"],
            )
        )

    def test_include_terms_restrict_when_configured(self):
        self.assertFalse(
            should_keep_article(
                title="Markets today",
                excerpt="",
                include_terms=["ai"],
                include_terms_2=[],
                exclude_terms=[],
            )
        )

    def test_secondary_include_terms_do_not_qualify_when_primary_is_empty(self):
        self.assertFalse(
            should_keep_article(
                title="Markets today",
                excerpt="",
                include_terms=[],
                include_terms_2=["ai"],
                exclude_terms=[],
            )
        )
        self.assertFalse(
            should_keep_article(
                title="AI markets today",
                excerpt="",
                include_terms=[],
                include_terms_2=["ai"],
                exclude_terms=[],
            )
        )

    def test_include_terms_and_mode_when_secondary_include_terms_present(self):
        self.assertTrue(
            should_keep_article(
                title="AI policy for chip startups",
                excerpt="",
                include_terms=["ai"],
                include_terms_2=["chip"],
                exclude_terms=[],
            )
        )
        self.assertFalse(
            should_keep_article(
                title="AI policy update",
                excerpt="",
                include_terms=["ai"],
                include_terms_2=["chip"],
                exclude_terms=[],
            )
        )

    def test_article_relevance_weights_title_more_than_excerpt(self):
        title_score = score_article_relevance(
            title="AI policy update",
            excerpt="",
            content="",
            include_terms=["ai"],
            include_terms_2=[],
            exclude_terms=[],
        )
        excerpt_score = score_article_relevance(
            title="",
            excerpt="AI policy update",
            content="",
            include_terms=["ai"],
            include_terms_2=[],
            exclude_terms=[],
        )
        self.assertGreater(title_score, excerpt_score)

    def test_article_relevance_applies_exclude_penalty(self):
        score = score_article_relevance(
            title="AI policy update",
            excerpt="sports conflict",
            content="",
            include_terms=["ai"],
            include_terms_2=[],
            exclude_terms=["sports"],
        )
        self.assertLess(score, 0.5)

    def test_article_relevance_scores_secondary_include_terms_same_as_primary(self):
        primary = score_article_relevance(
            title="AI policy update",
            excerpt="",
            content="",
            include_terms=["ai"],
            include_terms_2=[],
            exclude_terms=[],
        )
        secondary = score_article_relevance(
            title="AI policy update",
            excerpt="",
            content="",
            include_terms=[],
            include_terms_2=["ai"],
            exclude_terms=[],
        )
        self.assertEqual(primary, secondary)

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

    def test_find_cluster_qualifying_terms_combines_include_lists(self):
        matched = find_cluster_qualifying_terms(
            texts=["Space startup adopts AI tooling"],
            include_terms=["ai"],
            include_terms_2=["space"],
        )
        self.assertEqual(matched, ["ai", "space"])

    def test_qualifying_terms_snapshot_round_trip(self):
        raw = serialize_qualifying_terms_snapshot(["ai", "space"])
        parsed = deserialize_qualifying_terms_snapshot(raw)
        self.assertEqual(parsed, ["ai", "space"])

    def test_qualifying_terms_snapshot_invalid_payload(self):
        parsed = deserialize_qualifying_terms_snapshot("not-json")
        self.assertEqual(parsed, [])


if __name__ == "__main__":
    unittest.main()
