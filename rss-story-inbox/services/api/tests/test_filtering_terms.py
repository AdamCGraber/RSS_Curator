import unittest

from app.services.filtering.terms import parse_terms, should_keep_article


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


if __name__ == "__main__":
    unittest.main()
