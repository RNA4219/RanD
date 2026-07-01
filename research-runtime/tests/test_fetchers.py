import unittest
from pathlib import Path

from unittest.mock import patch

from rand_research.fetchers import build_kano_query_seed_items, collect_kano_shadow_search, parse_arxiv_recent_html, parse_generic_links, parse_kano_fixture_json, parse_rss_items


FIXTURE_ROOT = Path(__file__).parent / 'fixtures'


class FetcherTests(unittest.TestCase):
    def test_parse_arxiv_recent_html_from_fixture(self) -> None:
        html = (FIXTURE_ROOT / 'arxiv_recent.html').read_text(encoding='utf-8')
        items = parse_arxiv_recent_html({"name": "arxiv", "url": "https://arxiv.org/list/cs.AI/recent"}, html, 5)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].title, 'Sample Paper')
        self.assertEqual(items[0].authors, ['Alice', 'Bob'])
        self.assertEqual(items[1].title, '2501.00002')
        self.assertEqual(items[1].authors, [])

    def test_parse_rss_items_from_fixture(self) -> None:
        rss = (FIXTURE_ROOT / 'openai_news_rss.xml').read_text(encoding='utf-8')
        items = parse_rss_items({"name": "news", "kind": "news", "url": "https://example.com"}, rss, 3)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, 'OpenAI News Item')
        self.assertEqual(items[0].summary, 'Important OpenAI update.')

    def test_parse_rss_items_handles_empty_description(self) -> None:
        rss = (FIXTURE_ROOT / 'anthropic_news_rss.xml').read_text(encoding='utf-8')
        items = parse_rss_items({"name": "news", "kind": "news", "url": "https://example.com"}, rss, 3)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].summary, '')

    def test_parse_generic_links_from_fixture(self) -> None:
        html = (FIXTURE_ROOT / 'generic_links.html').read_text(encoding='utf-8')
        items = parse_generic_links(
            {"name": "generic", "kind": "paper", "url": "https://example.com", "link_pattern": "/papers/"},
            html,
            5,
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, 'Alpha Paper')

    def test_parse_generic_links_returns_empty_on_pattern_mismatch(self) -> None:
        html = (FIXTURE_ROOT / 'generic_links.html').read_text(encoding='utf-8')
        items = parse_generic_links(
            {"name": "generic", "kind": "paper", "url": "https://example.com", "link_pattern": "/missing/"},
            html,
            5,
        )
        self.assertEqual(items, [])

    def test_build_kano_query_seed_items(self) -> None:
        items = build_kano_query_seed_items(
            {
                "name": "kano_seed",
                "topic": "RanD KanoMode",
                "locales": ["ja-JP"],
                "query_families": [
                    {
                        "name": "complaints",
                        "candidate_id": "setup",
                        "kano_type": "must_be",
                        "requirement_statement": "証拠不足を明示する",
                        "templates": {"ja-JP": "{topic} 不満 必須"},
                    }
                ],
            },
            3,
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].metadata["source_type"], "complaints")
        self.assertEqual(items[0].metadata["locale"], "ja-JP")
        self.assertEqual(items[0].metadata["kano_type"], "must_be")
        self.assertIn("query://", items[0].url)

    def test_parse_kano_fixture_json(self) -> None:
        items = parse_kano_fixture_json({"name": "kano_fixture"}, FIXTURE_ROOT / "kano_evidence.json", 2)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].metadata["kano_candidate_id"], "setup-and-evidence-must-be")
        self.assertEqual(items[0].metadata["source_tier"], "user_signal")
        self.assertEqual(items[1].metadata["source_tier"], "primary")

    def test_kano_shadow_search_disabled_by_default(self) -> None:
        items = collect_kano_shadow_search({"name": "shadow"}, "agent", 1, 3)
        self.assertEqual(items, [])

    def test_kano_shadow_search_collects_live_like_links_when_enabled(self) -> None:
        html = '<html><body><a href="/review">Useful workflow comparison</a></body></html>'
        source = {
            "name": "shadow",
            "urls": [
                {
                    "url": "https://example.com/search?q=rand",
                    "metadata": {
                        "source_type": "compare",
                        "source_tier": "comparison",
                        "locale": "en-US",
                        "kano_type": "performance",
                        "kano_candidate_id": "competitive-baseline-performance",
                    },
                }
            ],
        }

        with patch.dict("os.environ", {"RAND_KANO_SHADOW_SEARCH": "1"}), patch("rand_research.fetchers.fetch_text", return_value=html):
            items = collect_kano_shadow_search(source, "agent", 1, 3)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].kind, "kano_evidence")
        self.assertEqual(items[0].metadata["source_type"], "compare")
        self.assertEqual(items[0].metadata["kano_type"], "performance")
        self.assertEqual(items[0].metadata["kano_candidate_id"], "competitive-baseline-performance")


if __name__ == "__main__":
    unittest.main()
