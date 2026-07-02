from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rand_research.pilot_snapshot import review_pilot_snapshot, write_pilot_snapshot
from rand_research.pilot_status import build_pilot_status, build_pilot_status_summary


class PilotStatusTests(unittest.TestCase):
    def test_status_recommends_snapshot_and_outbox_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_valid_run(root)
            self._write_operations(root, pending=True)

            with patch("rand_research.pilot_health.load_heartbeat_config", return_value=self._heartbeat_config()):
                status = build_pilot_status(root)

            step_names = [step["name"] for step in status["next_steps"]]
            self.assertEqual(status["status"], "degraded")
            self.assertIn("review_outbox", step_names)
            self.assertIn("capture_snapshot", step_names)
            self.assertEqual(status["pending_outbox_count"], 1)

    def test_status_recommends_review_for_unreviewed_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_valid_run(root)
            self._write_operations(root, pending=False)

            with patch("rand_research.pilot_health.load_heartbeat_config", return_value=self._heartbeat_config()):
                write_pilot_snapshot(root)
                status = build_pilot_status(root)

            step_names = [step["name"] for step in status["next_steps"]]
            self.assertEqual(status["status"], "go")
            self.assertIn("record_review", step_names)

    def test_status_can_continue_after_reviewed_go_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_valid_run(root)
            self._write_operations(root, pending=False)

            with patch("rand_research.pilot_health.load_heartbeat_config", return_value=self._heartbeat_config()):
                result = write_pilot_snapshot(root)
                review_pilot_snapshot(Path(result["path"]), "accept", "tester")
                status = build_pilot_status(root)

            self.assertEqual(status["status"], "go")
            self.assertEqual(status["next_steps"][0]["name"], "continue_pilot")

    def test_status_can_continue_with_reviewed_degraded_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_valid_run(root)
            self._write_operations(root, pending=True)

            with patch("rand_research.pilot_health.load_heartbeat_config", return_value=self._heartbeat_config()):
                result = write_pilot_snapshot(root)
                review_pilot_snapshot(Path(result["path"]), "accept_with_review", "tester")
                status = build_pilot_status(root)

            step_names = [step["name"] for step in status["next_steps"]]
            self.assertEqual(status["status"], "degraded")
            self.assertTrue(status["review_covers_latest_snapshot"])
            self.assertEqual(status["latest_review_decision"], "accept_with_review")
            self.assertNotIn("review_outbox", step_names)
            self.assertEqual(status["next_steps"][0]["name"], "continue_pilot_with_review")

    def test_status_summary_returns_compact_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_valid_run(root)
            self._write_operations(root, pending=True)

            with patch("rand_research.pilot_health.load_heartbeat_config", return_value=self._heartbeat_config()):
                result = write_pilot_snapshot(root)
                review_pilot_snapshot(Path(result["path"]), "accept_with_review", "tester")
                summary = build_pilot_status_summary(root)

            self.assertEqual(summary["status"], "degraded")
            self.assertEqual(summary["pending_outbox_count"], 1)
            self.assertEqual(summary["latest_review_decision"], "accept_with_review")
            self.assertTrue(summary["review_covers_latest_snapshot"])
            self.assertEqual(summary["next_step"], "continue_pilot_with_review")

    def _write_valid_run(self, root: Path) -> None:
        run_id = "20260702-010000-ok"
        run_dir = root / "runs" / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "report.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "status": "ok",
                    "status_reason": [],
                    "state_context": {},
                    "artifacts": {},
                    "dependency_health": {},
                    "run_meta": {"run_id": run_id, "started_at": "2026-07-02T01:00:00+09:00"},
                }
            ),
            encoding="utf-8",
        )
        (run_dir / "downstream_handoff.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "handoff_id": f"rand:downstream-{run_id}",
                    "mode": "discovery",
                    "workflow_cookbook": {},
                    "manual_bb_test_harness": {},
                    "code_to_gate": {},
                    "tracker_bridge": {},
                    "status": "dry_run",
                    "delivery": {
                        "mode": "dry_run",
                        "attempted": False,
                        "sent": False,
                        "success": None,
                        "destination": "tracker_bridge",
                        "destination_verdict": None,
                        "error": None,
                    },
                    "error": None,
                }
            ),
            encoding="utf-8",
        )

    def _write_operations(self, root: Path, pending: bool) -> None:
        state = root / "state"
        state.mkdir()
        notifications = []
        if pending:
            notifications.append(
                {
                    "schema_version": "1.0",
                    "notification_id": "note-1",
                    "run_id": "20260702-010000-ok",
                    "preset": "paper_arxiv_ai_recent",
                    "status": "pending",
                    "attempts": 0,
                    "reply_text": "Pending notification",
                }
            )
        (state / "operations-state.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "dedupe_keys": [],
                    "notifications": notifications,
                    "replays": [],
                }
            ),
            encoding="utf-8",
        )

    def _heartbeat_config(self) -> dict:
        return {
            "timezone": "Asia/Tokyo",
            "default_preset": "paper_arxiv_ai_recent",
            "rules": [{"hours": [8], "preset": "ai_watch_daily"}],
        }


if __name__ == "__main__":
    unittest.main()
