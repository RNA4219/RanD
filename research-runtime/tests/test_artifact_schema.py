import json
import tempfile
import unittest
from pathlib import Path

from rand_research.artifact_schema import infer_artifact_type, validate_artifact_path, validate_artifact_payload
from rand_research.models import SCHEMA_VERSION


class ArtifactSchemaTests(unittest.TestCase):
    def test_validate_report_payload(self) -> None:
        result = validate_artifact_payload(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "ok",
                "status_reason": [],
                "state_context": {},
                "artifacts": {},
                "dependency_health": {},
            },
            "report",
        )

        self.assertEqual(result["status"], "ok")

    def test_validate_missing_required_field_fails(self) -> None:
        result = validate_artifact_payload({"schema_version": SCHEMA_VERSION}, "downstream_handoff")

        self.assertEqual(result["status"], "failed")
        self.assertIn("missing required field: handoff_id", [issue["message"] for issue in result["issues"]])

    def test_validate_nested_tracker_schema_version(self) -> None:
        result = validate_artifact_payload(
            {
                "schema_version": SCHEMA_VERSION,
                "events": [{"sync_id": "sync-1"}],
            },
            "tracker_sync",
        )

        self.assertEqual(result["status"], "failed")
        self.assertIn("events[0].schema_version must be 1.0", [issue["message"] for issue in result["issues"]])

    def test_validate_path_infers_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "operations-state.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "dedupe_keys": [],
                        "notifications": [],
                        "replays": [],
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(infer_artifact_type(path), "operations_state")
            self.assertEqual(validate_artifact_path(path)["status"], "ok")

    def test_validate_requirements_packet_requires_rand_ids_and_policy_proposal(self) -> None:
        result = validate_artifact_payload(
            {
                "schema_version": SCHEMA_VERSION,
                "packet_id": "rand:rp-run-1",
                "derived_from": "kano.json",
                "qeg_policy_hash_ref": "qeg:policyHash:unadopted-proposal",
                "product_context": {},
                "requirements": [
                    {
                        "requirement_id": "rand:REQ-001",
                        "gate_policy_proposal": {
                            "proposal": "hard_gate",
                            "policyHashRef": "qeg:policyHash:unadopted-proposal",
                            "source": "rand:test",
                        },
                    }
                ],
                "release_readiness_prelude": {},
            },
            "requirements_packet",
        )

        self.assertEqual(result["status"], "ok")

    def test_validate_requirements_packet_rejects_unprefixed_ids(self) -> None:
        result = validate_artifact_payload(
            {
                "schema_version": SCHEMA_VERSION,
                "packet_id": "rp-run-1",
                "derived_from": "kano.json",
                "qeg_policy_hash_ref": "qeg:policyHash:unadopted-proposal",
                "product_context": {},
                "requirements": [{"requirement_id": "REQ-001", "gate_policy_proposal": {}}],
                "release_readiness_prelude": {},
            },
            "requirements_packet",
        )

        messages = [issue["message"] for issue in result["issues"]]
        self.assertEqual(result["status"], "failed")
        self.assertIn("packet_id must use rand: prefix", messages)
        self.assertIn("requirements[0].requirement_id must use rand: prefix", messages)

    def test_validate_shadow_downstream_handoff_fixture(self) -> None:
        result = validate_artifact_payload(
            {
                "schema_version": SCHEMA_VERSION,
                "handoff_id": "rand:downstream-run-1",
                "mode": "requirements_packet",
                "workflow_cookbook": {"artifact_type": "task_seed_candidates", "items": []},
                "manual_bb_test_harness": {"artifact_type": "manual_test_model_seed", "requirements": []},
                "code_to_gate": {"artifact_type": "phase_contract_seed", "contracts": []},
                "tracker_bridge": {"artifact_type": "tracker_dry_run_issues", "issues": []},
                "status": "shadow",
                "delivery": {
                    "mode": "shadow",
                    "attempted": False,
                    "sent": False,
                    "success": None,
                    "destination": "tracker_bridge",
                    "destination_verdict": None,
                    "error": None,
                    "recorded": True,
                    "shadow_artifact": "downstream_handoff.json",
                },
                "error": None,
            },
            "downstream_handoff",
        )

        self.assertEqual(result["status"], "ok")

    def test_validate_downstream_handoff_rejects_unprefixed_id(self) -> None:
        result = validate_artifact_payload(
            {
                "schema_version": SCHEMA_VERSION,
                "handoff_id": "downstream-run-1",
                "mode": "requirements_packet",
                "workflow_cookbook": {},
                "manual_bb_test_harness": {},
                "code_to_gate": {},
                "tracker_bridge": {},
                "status": "shadow",
                "delivery": {"mode": "shadow"},
                "error": None,
            },
            "downstream_handoff",
        )

        self.assertEqual(result["status"], "failed")
        self.assertIn("handoff_id must use rand: prefix", [issue["message"] for issue in result["issues"]])


if __name__ == "__main__":
    unittest.main()
