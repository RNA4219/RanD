import json
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from rand_research.fetchers import (
    ShadowSearchError,
    build_kano_query_seed_items,
    collect_kano_shadow_search,
    collect_source,
    parse_arxiv_recent_html,
    parse_generic_links,
    parse_kano_fixture_json,
    parse_rss_items,
)
from rand_research.http_utils import HttpResponse
from rand_research.kano import build_kano_artifacts
from rand_research.models import NormalizedItem
from rand_research.pipeline import _dedupe_items

FIXTURE_ROOT = Path(__file__).parent / 'fixtures'


def rustxng_response(payload):
    return HttpResponse(json.dumps(payload).encode(), "application/json", "utf-8", "http://localhost/search")


class FetcherTests(unittest.TestCase):
    def test_rustxng_preserves_search_provenance_and_requires_review_even_with_page_text(self) -> None:
        source = {"name": "shadow", "fetcher": "kano_shadow_search", "topic": "WSL 2 & 日本語",
                  "locales": ["ja-JP", "en-US"], "include_raw_content": True,
                  "query_families": [{"name": "setup", "template": "{topic}", "kano_type": "must_be",
                                      "source_tier": "primary", "confidence": 0.95}]}
        hit = {"title": "WSL setup", "url": "https://docs.docker.com/desktop/features/wsl/",
               "content": "snippet", "engine": "mwmbl", "engines": ["mwmbl"], "raw_content": "page text",
               "review_status": "verified"}
        reply = rustxng_response({"results": [hit, hit, {"url": "javascript:void(0)", "title": "bad"}]})
        env = {"RAND_KANO_SHADOW_SEARCH": "1", "RAND_KANO_SEARCH_PROVIDER": "rustxng",
               "RAND_RUSTXNG_ENDPOINT": "http://localhost:8080/search"}
        with patch.dict("os.environ", env), patch("rand_research.fetchers.request_bytes", return_value=reply) as http:
            item, = collect_source(source, "test", 2, 4)
        self.assertEqual(http.call_count, 2)
        parsed = urlsplit(http.call_args_list[0].args[0])
        self.assertEqual((parsed.netloc, parsed.path), ("localhost:8080", "/search"))
        self.assertEqual(parse_qs(parsed.query), {"q": ["WSL 2 & 日本語"], "language": ["ja"], "format": ["json"],
                                                  "max_results": ["4"], "include_raw_content": ["1"]})
        self.assertEqual(http.call_args.kwargs["allowed_content_types"], {"application/json"})
        self.assertEqual((item.url, item.title, item.summary), (hit["url"], hit["title"], "snippet"))
        self.assertEqual(item.metadata["raw_content"], "page text")
        result = build_kano_artifacts([item], {}, "run")
        ev, = result["kano"]["kano_candidates"][0]["evidence"]
        self.assertEqual((ev["review_status"], ev["source_tier"], ev["search_provider"], ev["engines"]),
                         ("pending", "discovery", "rustxng", ["mwmbl"]))
        self.assertEqual(result["requirements_packet"]["requirements"], [])

    def test_rustxng_reports_failed_queries_and_keeps_successful_hits(self) -> None:
        source = {"name": "shadow", "fetcher": "kano_shadow_search", "provider": "rustxng",
                  "locales": ["en", "ja", "fr", "de"], "query_families": [{"name": "setup"}]}
        replies = [rustxng_response({"results": [], "unresponsive_engines": [["example", "timeout"]]}),
                   rustxng_response({"results": "invalid"}), rustxng_response({"results": []}),
                   rustxng_response({"results": [{"title": "Useful result", "url": "https://example.org/wsl"}]})]
        with patch.dict("os.environ", {"RAND_KANO_SHADOW_SEARCH": "1"}), patch("rand_research.fetchers.request_bytes", side_effect=replies) as http:
            with self.assertRaises(ShadowSearchError) as error:
                collect_source(source, "test", 2, 5)
        self.assertNotIn("include_raw_content", http.call_args.args[0])
        self.assertIn("timeout", str(error.exception))
        self.assertIn("results array", str(error.exception))
        self.assertEqual([item.url for item in error.exception.items], ["https://example.org/wsl"])

    def test_search_links_need_review_before_they_can_support_a_requirement(self) -> None:
        html = ('<a href="/httpservice/retry/enablejs">here</a>'
                '<a href="/search?retry=1">click here</a>'
                '<a href="https://support.google.com/websearch">feedback</a>')
        labels = {"kano_candidate_id": "wsl-setup", "kano_type": "must_be", "confidence": 0.99,
                  "source_tier": "user_signal", "bias_note": "ranking bias", "kill_condition": "irrelevant"}
        source = {"name": "shadow", "urls": [{"url": "https://www.google.com/search", "metadata": labels}]}
        with patch.dict("os.environ", {"RAND_KANO_SHADOW_SEARCH": "1"}), patch("rand_research.fetchers.fetch_text", return_value=html):
            hits = collect_kano_shadow_search(source, "test", 1, 5)
        self.assertEqual(len(hits), 3)
        raw = build_kano_artifacts(hits, {}, "run")
        self.assertEqual(raw["requirements_packet"]["requirements"], [])
        self.assertEqual(raw["kano"]["source_summary"]["user_signal_count"], 0)
        self.assertEqual(raw["kano"]["source_summary"]["pending_count"], 3)

        # A replay of an old shadow result lacks an explicit review status.
        hits[0].metadata.pop("review_status")
        hits[0].metadata["source_tier"] = "user_signal"
        hits[1].metadata.update(review_status="excluded")
        hits[2].url = "https://docs.docker.com/desktop/features/wsl/"
        verified = NormalizedItem(**hits[2].to_dict())
        verified.metadata.update(review_status="verified", source_tier="primary", kano_type="performance", confidence=0.74)
        verified.summary = "The source text was reviewed."
        for ordered in ([*hits, verified], [verified, *hits]):
            artifacts = build_kano_artifacts(_dedupe_items(ordered), {}, "mixed")
            req, = artifacts["requirements_packet"]["requirements"]
            self.assertEqual((req["kano_type"], req["confidence"]), ("performance", 0.74))
            self.assertEqual(len(req["evidence_refs"]), 2)
            self.assertEqual(artifacts["kano"]["source_summary"]["excluded_count"], 1)

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
