import json
import tempfile
import unittest
from pathlib import Path

from rand_research.state_store import build_execution_context


class StateStoreTests(unittest.TestCase):
    def test_build_execution_context_reads_prior_task_and_memory_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            state_path = root / "taskstate.json"
            memory_path = root / "memx-journal.json"

            state_path.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "task-1",
                                "run_id": "run-1",
                                "preset": "paper_arxiv_ai_recent",
                                "status": "done",
                                "updated_at": "2026-03-15T00:00:00Z",
                                "summary": "first",
                            },
                            {
                                "task_id": "task-2",
                                "run_id": "run-2",
                                "preset": "paper_arxiv_ai_recent",
                                "status": "running",
                                "updated_at": "2026-03-16T00:00:00Z",
                                "summary": "second",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            memory_path.write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "entry_id": "memx-run-1",
                                "scope": "rand:paper_arxiv_ai_recent",
                                "recorded_at": "2026-03-16T00:00:00Z",
                                "summary": "remembered",
                                "sources": ["https://arxiv.org/abs/1", "https://arxiv.org/abs/2"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            context = build_execution_context(state_path, memory_path, "paper_arxiv_ai_recent")

            self.assertEqual(context.previous_run_count, 2)
            self.assertEqual(len(context.open_tasks), 1)
            self.assertIn("https://arxiv.org/abs/1", context.known_urls)
            self.assertEqual(context.recent_tasks[0]["task_id"], "task-2")


if __name__ == "__main__":
    unittest.main()
