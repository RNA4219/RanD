import json
import unittest
from unittest.mock import patch

from rand_research import cli


class HeartbeatCliTests(unittest.TestCase):
    def test_select_preset_by_time_uses_configured_rule(self) -> None:
        with patch.object(cli, "load_heartbeat_config", return_value={
            "timezone": "Asia/Tokyo",
            "default_preset": "paper_arxiv_ai_recent",
            "rules": [{"hours": [8, 9, 10], "preset": "ai_watch_daily"}],
        }):
            with patch("rand_research.cli.datetime") as mock_datetime:
                mock_now = mock_datetime.now.return_value
                mock_now.hour = 9
                self.assertEqual(cli._select_preset_by_time(), "ai_watch_daily")

    def test_build_summary_includes_status_and_counts(self) -> None:
        report = {
            "status": "degraded",
            "status_reason": ["insight_failed"],
            "collected_items": [{"title": "A", "url": "https://example.com/a"}],
            "state_context": {
                "before": {"open_tasks": [{"task_id": "1"}]},
                "after": {"open_tasks": [{"task_id": "1"}, {"task_id": "2"}]},
            },
        }
        summary = cli._build_summary(report, "ai_watch_daily")
        self.assertEqual(summary["preset"], "ai_watch_daily")
        self.assertEqual(summary["status"], "degraded")
        self.assertEqual(summary["open_tasks_before"], 1)
        self.assertEqual(summary["open_tasks_after"], 2)
        self.assertEqual(summary["top_items"][0]["title"], "A")


if __name__ == "__main__":
    unittest.main()
