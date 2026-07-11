from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rand_research.artifact_schema import validate_artifact_path
from rand_research.pilot_snapshot import (
    accept_current_pilot_state,
    build_pilot_snapshot,
    review_pilot_snapshot,
    write_pilot_snapshot,
)


class PilotSnapshotTests(unittest.TestCase):
    def test_build_snapshot_includes_readiness_outbox_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_valid_run(root)
            self._write_operations(root, pending=True)

            with patch("rand_research.pilot_health.load_heartbeat_config", return_value=self._heartbeat_config()):
                snapshot = build_pilot_snapshot(root)

            self.assertEqual(snapshot["type"], "pilot_snapshot")
            self.assertEqual(snapshot["status"], "degraded")
            self.assertTrue(snapshot["review_required"])
            self.assertEqual(snapshot["outbox_plan"]["pending_count"], 1)
            self.assertEqual(snapshot["metrics"]["run_count"], 1)

    def test_write_snapshot_creates_valid_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_valid_run(root)
            self._write_operations(root, pending=False)
            out = root / "snapshot.json"

            with patch("rand_research.pilot_health.load_heartbeat_config", return_value=self._heartbeat_config()):
                result = write_pilot_snapshot(root, out)

            self.assertEqual(result["status"], "written")
            self.assertTrue(out.exists())
            validation = validate_artifact_path(out, "pilot_snapshot")
            self.assertEqual(validation["status"], "ok")

    def test_review_snapshot_creates_followup_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_valid_run(root)
            self._write_operations(root, pending=True)
            snapshot_path = root / "pilot-snapshot-test.json"

            with patch("rand_research.pilot_health.load_heartbeat_config", return_value=self._heartbeat_config()):
                write_pilot_snapshot(root, snapshot_path)
                result = review_pilot_snapshot(
                    snapshot_path,
                    decision="accept_with_review",
                    reviewer="tester",
                    notes="pending notification is acceptable for pilot",
                )

            review_path = Path(result["path"])
            self.assertTrue(review_path.exists())
            self.assertEqual(result["review"]["decision"], "accept_with_review")
            self.assertTrue(result["review"]["review_required"])
            self.assertTrue(result["review"]["required_followups"])
            validation = validate_artifact_path(review_path)
            self.assertEqual(validation["artifact_type"], "pilot_review")
            self.assertEqual(validation["status"], "ok")

    def test_accept_current_pilot_state_writes_snapshot_and_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_valid_run(root)
            self._write_operations(root, pending=True)

            with patch("rand_research.pilot_health.load_heartbeat_config", return_value=self._heartbeat_config()):
                result = accept_current_pilot_state(
                    root,
                    decision="accept_with_review",
                    reviewer="tester",
                    notes="accepted for pilot",
                )

            snapshot_path = Path(result["snapshot_path"])
            review_path = Path(result["review_path"])
            self.assertTrue(snapshot_path.exists())
            self.assertTrue(review_path.exists())
            self.assertEqual(result["snapshot_status"], "degraded")
            self.assertEqual(result["decision"], "accept_with_review")
            self.assertGreater(result["required_followup_count"], 0)
            self.assertEqual(result["review"]["snapshot_ref"]["path"], str(snapshot_path))

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
