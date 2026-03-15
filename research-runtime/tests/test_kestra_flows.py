import unittest
from pathlib import Path


class KestraFlowContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[2] / "kestra" / "flows"

    def test_daily_and_nightly_flows_define_jst_timezone(self) -> None:
        daily = (self.root / "research-ai-watch-daily.yaml").read_text(encoding="utf-8")
        nightly = (self.root / "research-arxiv-nightly.yaml").read_text(encoding="utf-8")
        self.assertIn('timezone: "Asia/Tokyo"', daily)
        self.assertIn('timezone: "Asia/Tokyo"', nightly)

    def test_heartbeat_flow_has_no_schedule_trigger_and_no_utc_window_logic(self) -> None:
        heartbeat = (self.root / "research-heartbeat.yaml").read_text(encoding="utf-8")
        self.assertNotIn('type: io.kestra.plugin.core.trigger.Schedule', heartbeat)
        self.assertNotIn('hour == 23', heartbeat)
        self.assertNotIn('hour == 17', heartbeat)
        self.assertNotIn('scheduled_morning_watch', heartbeat)
        self.assertNotIn('scheduled_night_papers', heartbeat)
        self.assertIn('configs" / "heartbeat.json"', heartbeat)
        self.assertIn('from zoneinfo import ZoneInfo', heartbeat)


if __name__ == "__main__":
    unittest.main()
