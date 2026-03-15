import unittest
from pathlib import Path

from rand_research.fetchers import parse_arxiv_recent_html, parse_generic_links, parse_rss_items


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


if __name__ == "__main__":
    unittest.main()
