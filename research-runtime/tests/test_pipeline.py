import unittest

from rand_research.models import ExecutionContext, NormalizedItem
from rand_research.pipeline import _apply_execution_context, _dedupe_items, _final_status


class PipelineTests(unittest.TestCase):
    def test_dedupe_items(self) -> None:
        items = [
            NormalizedItem(id="1", kind="paper", source_name="a", url="https://x", title="a"),
            NormalizedItem(id="2", kind="paper", source_name="b", url="https://x", title="b"),
        ]
        deduped = _dedupe_items(items)
        self.assertEqual(len(deduped), 1)

    def test_apply_execution_context_marks_seen_items(self) -> None:
        items = [
            NormalizedItem(id="1", kind="paper", source_name="a", url="https://seen", title="seen", priority=8, high_priority=True),
            NormalizedItem(id="2", kind="paper", source_name="b", url="https://new", title="new", priority=5, high_priority=True),
        ]
        context = ExecutionContext(preset="paper_arxiv_ai_recent", previous_run_count=2, known_urls=["https://seen"])

        enriched = _apply_execution_context(items, context)

        self.assertEqual(enriched[0].url, "https://new")
        self.assertFalse(enriched[1].high_priority)
        self.assertTrue(enriched[1].metadata["seen_before"])
        self.assertIn("previously_seen", enriched[1].tags)

    def test_final_status_returns_failed_for_source_failure(self) -> None:
        dependency_health = {
            "sources": "failed",
            "state": "ok",
            "insight": "ok",
            "gate": "ok",
            "memx": "ok",
            "tracker": "ok",
        }
        self.assertEqual(_final_status(dependency_health, []), "failed")

    def test_final_status_returns_degraded_for_partial_dependency_failure(self) -> None:
        dependency_health = {
            "sources": "ok",
            "state": "ok",
            "insight": "degraded",
            "gate": "ok",
            "memx": "ok",
            "tracker": "ok",
        }
        self.assertEqual(_final_status(dependency_health, []), "degraded")


if __name__ == "__main__":
    unittest.main()
