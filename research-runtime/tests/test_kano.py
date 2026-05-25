import unittest

from rand_research.kano import build_kano_artifacts
from rand_research.models import NormalizedItem, SCHEMA_VERSION


class KanoTests(unittest.TestCase):
    def test_build_kano_artifacts_promotes_complete_candidates(self) -> None:
        items = [
            NormalizedItem(
                id="ev-1",
                kind="kano_evidence",
                source_name="fixture",
                url="fixture://1",
                title="証拠不足を明示する",
                summary="証拠不足のまま要求化すると危ない。",
                metadata={
                    "kano_candidate_id": "safe-packet",
                    "kano_type": "must_be",
                    "source_type": "complaints",
                    "source_tier": "user_signal",
                    "locale": "ja-JP",
                    "confidence": 0.82,
                    "bias_note": "不満はネガティブに偏る。",
                    "kill_condition": "レビューで不要と判断されたら外す。",
                    "requirement_statement": "KanoMode は証拠不足を明示しなければならない。",
                },
            )
        ]

        artifacts = build_kano_artifacts(items, {"name": "kano_requirements_offline_eval"}, "run-1")

        self.assertEqual(artifacts["kano"]["schema_version"], SCHEMA_VERSION)
        self.assertEqual(artifacts["requirements_packet"]["schema_version"], SCHEMA_VERSION)
        self.assertEqual(artifacts["kano"]["kano_candidates"][0]["kano_type"], "must_be")
        requirement = artifacts["requirements_packet"]["requirements"][0]
        self.assertEqual(requirement["priority"], "P0")
        self.assertEqual(requirement["gate_policy"], "hard_gate")

    def test_build_kano_artifacts_does_not_promote_missing_safety_fields(self) -> None:
        items = [
            NormalizedItem(
                id="ev-1",
                kind="kano_evidence",
                source_name="fixture",
                url="fixture://1",
                title="KPI 草案が便利",
                summary="KPI 草案があるとよい。",
                metadata={
                    "kano_candidate_id": "kpi",
                    "kano_type": "attractive",
                    "confidence": 0.7,
                    "requirement_statement": "KPI 草案を付けられるとよい。",
                },
            )
        ]

        artifacts = build_kano_artifacts(items, {"name": "kano_requirements_offline_eval"}, "run-1")

        self.assertEqual(len(artifacts["kano"]["kano_candidates"]), 1)
        self.assertEqual(artifacts["requirements_packet"]["requirements"], [])


if __name__ == "__main__":
    unittest.main()
