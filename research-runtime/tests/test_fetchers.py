import unittest

from rand_research.fetchers import parse_arxiv_recent_html, parse_rss_items


class FetcherTests(unittest.TestCase):
    def test_parse_arxiv_recent_html(self) -> None:
        html = """
        <dl>
        <dt><a href="/abs/2501.00001">abs</a></dt>
        <dd>
          <div class="list-title mathjax">Title: Sample Paper</div>
          <div class="list-authors"><a href="/search/?searchtype=author">Alice</a>, <a href="/search/?searchtype=author">Bob</a></div>
          <p class="mathjax">This paper studies agents.</p>
        </dd>
        </dl>
        """
        items = parse_arxiv_recent_html({"name": "arxiv", "url": "https://arxiv.org/list/cs.AI/recent"}, html, 5)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Sample Paper")
        self.assertEqual(items[0].authors, ["Alice", "Bob"])

    def test_parse_rss_items(self) -> None:
        rss = """
        <rss><channel>
          <item>
            <title>News Item</title>
            <link>https://example.com/news</link>
            <description>Important update.</description>
            <pubDate>Mon, 01 Jan 2026 00:00:00 GMT</pubDate>
          </item>
        </channel></rss>
        """
        items = parse_rss_items({"name": "news", "kind": "news", "url": "https://example.com"}, rss, 3)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "News Item")


if __name__ == "__main__":
    unittest.main()
