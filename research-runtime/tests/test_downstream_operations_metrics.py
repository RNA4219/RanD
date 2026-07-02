import json
import tempfile
import unittest
from pathlib import Path

from rand_research.downstream import build_downstream_handoff
from rand_research.metrics import collect_metrics
from rand_research.models import SCHEMA_VERSION
from rand_research.operations import (
    build_outbox_plan,
    mark_notification_attempt,
    pending_resend_payloads,
    plan_replay,
    record_notification_outbox,
)
from rand_research.review_tools import build_shadow_eval_template, build_tracker_review, generate_task_seed_drafts, render_shadow_eval_csv


class DownstreamHandoffTests(unittest.TestCase):
    def test_build_downstream_handoff_from_requirements_packet(self) -> None:
        packet = {
            "schema_version": SCHEMA_VERSION,
            "requirements": [
                {
                    "requirement_id": "rand:REQ-001",
                    "title": "Evidence safety",
                    "statement": "Evidence must be explicit.",
                    "priority": "P0",
                    "acceptance_criteria": ["has evidence"],
                    "evidence_refs": ["KC-001", "EV-001"],
                    "risks": ["bias"],
                    "gate_policy_proposal": {
                        "proposal": "hard_gate",
                        "policyHashRef": "qeg:policyHash:unadopted-proposal",
                        "source": "rand:test",
                    },
                    "confidence": 0.9,
                    "kano_type": "must_be",
                }
            ],
        }

        handoff = build_downstream_handoff({"requirements_packet": packet}, "run-1")

        self.assertIsNotNone(handoff)
        assert handoff is not None
        self.assertEqual(handoff["status"], "dry_run")
        self.assertEqual(handoff["handoff_id"], "rand:downstream-run-1")
        self.assertEqual(handoff["delivery"]["mode"], "dry_run")
        self.assertFalse(handoff["delivery"]["sent"])
        self.assertEqual(handoff["workflow_cookbook"]["items"][0]["priority"], "P0")
        self.assertEqual(handoff["manual_bb_test_harness"]["requirements"][0]["requirement_id"], "rand:REQ-001")
        self.assertEqual(handoff["code_to_gate"]["contracts"][0]["gate_policy_proposal"]["proposal"], "hard_gate")
        self.assertEqual(handoff["tracker_bridge"]["issues"][0]["labels"], ["rand", "requirements", "kano:must_be"])

    def test_shadow_handoff_records_without_sending(self) -> None:
        handoff = build_downstream_handoff({"requirements_packet": {"schema_version": SCHEMA_VERSION, "requirements": []}}, "run-1", mode="shadow")

        self.assertIsNotNone(handoff)
        assert handoff is not None
        self.assertEqual(handoff["status"], "shadow")
        self.assertTrue(handoff["delivery"]["recorded"])
        self.assertFalse(handoff["delivery"]["sent"])

    def test_live_handoff_records_transport_result(self) -> None:
        def transport(payload: dict[str, object]) -> dict[str, object]:
            self.assertEqual(payload["handoff_id"], "rand:downstream-run-1")
            return {
                "sent": True,
                "success": True,
                "destination_verdict": "accepted",
                "accepted_by": "tracker-bridge",
                "response_ref": "tracker:sync-1",
            }

        handoff = build_downstream_handoff(
            {"requirements_packet": {"schema_version": SCHEMA_VERSION, "requirements": []}},
            "run-1",
            mode="live",
            transport=transport,
        )

        self.assertIsNotNone(handoff)
        assert handoff is not None
        self.assertTrue(handoff["delivery"]["sent"])
        self.assertTrue(handoff["delivery"]["success"])
        self.assertEqual(handoff["delivery"]["destination_verdict"], "accepted")


class ReviewToolsTests(unittest.TestCase):
    def test_shadow_eval_template_and_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "kano.json").write_text(
                json.dumps(
                    {
                        "request_id": "kano-run-1",
                        "topic": "Shadow test",
                        "kano_candidates": [
                            {
                                "candidate_id": "KC-001",
                                "statement": "Evidence must be reviewed.",
                                "kano_type": "must_be",
                                "evidence": [
                                    {
                                        "evidence_id": "EV-001",
                                        "source_ref": "https://example.com/a",
                                        "source_type": "complaints",
                                        "source_tier": "user_signal",
                                        "locale": "en-US",
                                        "summary": "A complaint.",
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            template = build_shadow_eval_template(run_dir)
            csv_text = render_shadow_eval_csv(template)

            self.assertEqual(template["rows"][0]["promote_decision"], "pending")
            self.assertIn("relevance_score_1_5", csv_text)
            self.assertIn("EV-001", csv_text)

    def test_tracker_review_from_downstream_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "downstream_handoff.json"
            path.write_text(
                json.dumps(
                    {
                        "tracker_bridge": {
                            "issues": [
                                {
                                    "title": "Issue A",
                                    "body": "Body",
                                    "labels": ["rand"],
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            review = build_tracker_review(path)

            self.assertEqual(review["issue_count"], 1)
            self.assertEqual(review["issues"][0]["review_decision"], "pending")
            self.assertFalse(review["issues"][0]["ready_to_send"])

    def test_generate_task_seed_drafts_dry_run_and_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            handoff = root / "downstream_handoff.json"
            out_dir = root / "tasks"
            handoff.write_text(
                json.dumps(
                    {
                        "workflow_cookbook": {
                            "items": [
                                {
                                    "title": "Evidence safety",
                                    "objective": "Make evidence explicit.",
                                    "priority": "P0",
                                    "acceptance": ["Has evidence refs"],
                                    "evidence_refs": ["EV-001"],
                                    "risks": ["bias"],
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            dry_run = generate_task_seed_drafts(handoff, out_dir, dry_run=True)
            written = generate_task_seed_drafts(handoff, out_dir, dry_run=False)

            self.assertEqual(dry_run["status"], "dry_run")
            self.assertIn("content", dry_run["drafts"][0])
            self.assertEqual(written["status"], "written")
            self.assertTrue(Path(written["drafts"][0]["path"]).exists())


class OperationsTests(unittest.TestCase):
    def test_notification_outbox_and_dedupe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "operations.json"
            report = {
                "status": "ok",
                "run_meta": {"run_id": "run-1", "preset": "paper_arxiv_ai_recent"},
                "operational_summary": {"item_count": 1},
                "collected_items": [{"title": "A"}],
            }

            first = record_notification_outbox(path, "run-1", "paper_arxiv_ai_recent", report, {})
            second = record_notification_outbox(path, "run-1", "paper_arxiv_ai_recent", report, {})
            pending = pending_resend_payloads(path)

            self.assertEqual(first["status"], "pending")
            self.assertEqual(second["status"], "duplicate_suppressed")
            self.assertEqual(pending["pending_count"], 1)

            marked = mark_notification_attempt(path, first["notification_id"], "sent")
            self.assertEqual(marked["status"], "sent")
            self.assertEqual(marked["attempts"], 1)

    def test_replay_plan_from_taskstate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            taskstate = root / "taskstate.json"
            operations = root / "operations.json"
            taskstate.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "task-run-1",
                                "run_id": "run-1",
                                "preset": "paper_arxiv_ai_recent",
                                "status": "needs_review",
                                "artifacts": {"report_json": "runs/run-1/report.json"},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            plan = plan_replay(taskstate, operations, "task-run-1")

            self.assertEqual(plan["status"], "planned")
            self.assertEqual(plan["resume_from"], "notify")

    def test_outbox_plan_recommends_review_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "operations.json"
            path.write_text(
                json.dumps(
                    {
                        "notifications": [
                            {
                                "notification_id": "note-fresh",
                                "run_id": "run-1",
                                "preset": "paper_arxiv_ai_recent",
                                "status": "pending",
                                "attempts": 0,
                                "reply_text": "Fresh pending",
                            },
                            {
                                "notification_id": "note-attempted",
                                "run_id": "run-2",
                                "preset": "paper_arxiv_ai_recent",
                                "status": "pending",
                                "attempts": 1,
                                "reply_text": "Attempted pending",
                            },
                            {
                                "notification_id": "note-failed",
                                "run_id": "run-3",
                                "preset": "paper_arxiv_ai_recent",
                                "status": "failed",
                                "attempts": 2,
                                "error": "webhook timeout",
                                "reply_text": "Failed pending",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            plan = build_outbox_plan(path)

            self.assertEqual(plan["pending_count"], 3)
            actions = {item["notification_id"]: item["recommended_action"] for item in plan["actions"]}
            self.assertEqual(actions["note-fresh"], "send_or_mark_sent")
            self.assertEqual(actions["note-attempted"], "confirm_delivery")
            self.assertEqual(actions["note-failed"], "review_failure")
            self.assertEqual(plan["action_counts"]["send_or_mark_sent"], 1)


class MetricsTests(unittest.TestCase):
    def test_collect_metrics_from_runs_and_operations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "runs" / "run-1"
            run_dir.mkdir(parents=True)
            (run_dir / "report.json").write_text(
                json.dumps(
                    {
                        "status": "degraded",
                        "status_reason": ["state_write_failed"],
                        "run_meta": {"started_at": "2026-07-01T00:00:00Z"},
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "downstream_handoff.json").write_text(
                json.dumps(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "handoff_id": "rand:downstream-run-1",
                        "status": "live",
                        "delivery": {
                            "mode": "live",
                            "success": False,
                            "destination_verdict": "rejected",
                        },
                    }
                ),
                encoding="utf-8",
            )
            state = root / "state"
            state.mkdir()
            (state / "operations-state.json").write_text(
                json.dumps(
                    {
                        "notifications": [{"status": "pending"}, {"status": "duplicate_suppressed"}],
                        "replays": [{"status": "planned"}],
                    }
                ),
                encoding="utf-8",
            )
            (state / "tracker-sync.json").write_text(json.dumps({"events": [{"status": "degraded"}]}), encoding="utf-8")

            metrics = collect_metrics(root)

            self.assertEqual(metrics["run_count"], 1)
            self.assertEqual(metrics["status_counts"]["degraded"], 1)
            self.assertEqual(metrics["state_write_failed_count"], 1)
            self.assertEqual(metrics["pending_notification_count"], 1)
            self.assertEqual(metrics["duplicate_suppression_count"], 1)
            self.assertEqual(metrics["tracker_sync_failure_count"], 1)
            self.assertEqual(metrics["downstream_handoff_count"], 1)
            self.assertEqual(metrics["downstream_handoff_mode_counts"]["live"], 1)
            self.assertEqual(metrics["downstream_handoff_live_failure_count"], 1)
            self.assertEqual(metrics["downstream_handoff_destination_verdict_counts"]["rejected"], 1)


if __name__ == "__main__":
    unittest.main()
