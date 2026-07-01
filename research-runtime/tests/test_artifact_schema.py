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


if __name__ == "__main__":
    unittest.main()
