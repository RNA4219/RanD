import unittest

from rand_research.models import NormalizedItem
from rand_research.pipeline import _dedupe_items


class PipelineTests(unittest.TestCase):
    def test_dedupe_items(self) -> None:
        items = [
            NormalizedItem(id="1", kind="paper", source_name="a", url="https://x", title="a"),
            NormalizedItem(id="2", kind="paper", source_name="b", url="https://x", title="b"),
        ]
        deduped = _dedupe_items(items)
        self.assertEqual(len(deduped), 1)


if __name__ == "__main__":
    unittest.main()
