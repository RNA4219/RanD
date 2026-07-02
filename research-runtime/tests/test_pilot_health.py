from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rand_research.pilot_health import evaluate_pilot_readiness


class PilotHealthTests(unittest.TestCase):
    def test_pilot_check_go_for_valid_latest_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_run(root, "20260702-010000-ok", "ok", with_handoff=True)
            self._write_operations(root, notifications=[])

            with patch("rand_research.pilot_health.load_heartbeat_config", return_value=self._heartbeat_config()):
                result = evaluate_pilot_readiness(root)

            self.assertEqual(result["status"], "go")
            self.assertEqual(result["latest_run_id"], "20260702-010000-ok")
            self.assertTrue(all(check["level"] == "ok" for check in result["checks"]))

    def test_pilot_check_degraded_for_pending_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_run(root, "20260702-010000-ok", "ok", with_handoff=True)
            self._write_operations(
                root,
                notifications=[
                    {
                        "schema_version": "1.0",
                        "notification_id": "note-1",
                        "status": "pending",
                    }
                ],
            )

            with patch("rand_research.pilot_health.load_heartbeat_config", return_value=self._heartbeat_config()):
                result = evaluate_pilot_readiness(root)

            self.assertEqual(result["status"], "degraded")
            self.assertIn("notification_outbox", self._warn_names(result))

    def test_pilot_check_no_go_for_failed_latest_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_run(root, "20260702-010000-failed", "failed", with_handoff=False)
            self._write_operations(root, notifications=[])

            with patch("rand_research.pilot_health.load_heartbeat_config", return_value=self._heartbeat_config()):
                result = evaluate_pilot_readiness(root)

            self.assertEqual(result["status"], "no_go")
            self.assertIn("latest_report_status", self._fail_names(result))

    def _write_run(self, root: Path, run_id: str, status: str, with_handoff: bool) -> None:
        run_dir = root / "runs" / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "report.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "status": status,
                    "status_reason": ["source_failed"] if status == "failed" else [],
                    "state_context": {},
                    "artifacts": {},
                    "dependency_health": {},
                    "run_meta": {"run_id": run_id, "started_at": "2026-07-02T01:00:00+09:00"},
                }
            ),
            encoding="utf-8",
        )
        if with_handoff:
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

    def _write_operations(self, root: Path, notifications: list[dict]) -> None:
        state = root / "state"
        state.mkdir()
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

    def _warn_names(self, result: dict) -> set[str]:
        return {check["name"] for check in result["checks"] if check["level"] == "warn"}

    def _fail_names(self, result: dict) -> set[str]:
        return {check["name"] for check in result["checks"] if check["level"] == "fail"}


if __name__ == "__main__":
    unittest.main()
