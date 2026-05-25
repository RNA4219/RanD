import unittest

from rand_research.kano import build_audit_artifacts, build_kano_artifacts
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


class AuditTests(unittest.TestCase):
    def test_build_audit_artifacts_has_required_fields(self) -> None:
        items = [
            NormalizedItem(
                id="audit-req-001",
                kind="audit_evidence",
                source_name="audit_fixture",
                url="fixture://audit/req-001",
                title="preset実行導線の監査",
                summary="REQ-001: preset実行導線は仕様と一致。",
                metadata={
                    "requirement_id": "REQ-001",
                    "original_text": "KanoModeはpresetから起動できる。",
                    "source_type": "official",
                    "source_tier": "primary",
                    "locale": "ja-JP",
                    "kano_type": "must_be",
                    "confidence": 0.92,
                    "testability": "high",
                    "implementation_alignment": "high",
                },
            )
        ]

        artifacts = build_audit_artifacts(items, {"audit_topic": "Test Audit"}, "run-audit-1")

        audit_packet = artifacts["requirements_audit_packet"]
        self.assertEqual(audit_packet["schema_version"], SCHEMA_VERSION)
        self.assertIn("document_id", audit_packet)
        self.assertIn("summary", audit_packet)
        self.assertIn("requirements", audit_packet)
        self.assertIn("gate_summary", audit_packet)
        self.assertIn("source_refs", audit_packet)
        self.assertIn("assumptions", audit_packet)

    def test_audit_requirement_has_gate_verdict(self) -> None:
        items = [
            NormalizedItem(
                id="audit-req-002",
                kind="audit_evidence",
                source_name="audit_fixture",
                url="fixture://audit/req-002",
                title="validation監査",
                summary="REQ-002: validationロジック実装が部分的。",
                metadata={
                    "requirement_id": "REQ-002",
                    "original_text": "安全field必須化。",
                    "source_type": "official",
                    "source_tier": "primary",
                    "locale": "ja-JP",
                    "kano_type": "must_be",
                    "confidence": 0.78,
                    "testability": "high",
                    "implementation_alignment": "medium",
                },
            )
        ]

        artifacts = build_audit_artifacts(items, {"audit_topic": "Test Audit"}, "run-audit-1")

        requirement = artifacts["requirements_audit_packet"]["requirements"][0]
        self.assertIn("requirement_id", requirement)
        self.assertIn("original_text", requirement)
        self.assertIn("kano_estimate", requirement)
        self.assertIn("confidence", requirement)
        self.assertIn("evidence", requirement)
        self.assertIn("testability", requirement)
        self.assertIn("implementation_alignment", requirement)
        self.assertIn("risks", requirement)
        self.assertIn("issues", requirement)
        self.assertIn("suggested_action", requirement)
        self.assertIn("gate_verdict", requirement)

    def test_gate_verdict_go_for_high_alignment(self) -> None:
        items = [
            NormalizedItem(
                id="audit-go",
                kind="audit_evidence",
                source_name="audit_fixture",
                url="fixture://audit/go",
                title="良好な要件",
                summary="testabilityとimplementation_alignmentが高い。",
                metadata={
                    "requirement_id": "REQ-GO",
                    "original_text": "良好な要件。",
                    "source_type": "official",
                    "source_tier": "primary",
                    "locale": "ja-JP",
                    "kano_type": "must_be",
                    "confidence": 0.92,
                    "testability": "high",
                    "implementation_alignment": "high",
                },
            )
        ]

        artifacts = build_audit_artifacts(items, {"audit_topic": "Test"}, "run-1")
        self.assertEqual(artifacts["requirements_audit_packet"]["requirements"][0]["gate_verdict"], "go")

    def test_gate_verdict_conditional_go_for_medium_alignment(self) -> None:
        items = [
            NormalizedItem(
                id="audit-conditional",
                kind="audit_evidence",
                source_name="audit_fixture",
                url="fixture://audit/conditional",
                title="補強が必要な要件",
                summary="implementation_alignmentがmedium。",
                metadata={
                    "requirement_id": "REQ-CONDITIONAL",
                    "original_text": "補強が必要な要件。",
                    "source_type": "official",
                    "source_tier": "primary",
                    "locale": "ja-JP",
                    "kano_type": "must_be",
                    "confidence": 0.78,
                    "testability": "medium",
                    "implementation_alignment": "medium",
                },
            )
        ]

        artifacts = build_audit_artifacts(items, {"audit_topic": "Test"}, "run-1")
        self.assertEqual(artifacts["requirements_audit_packet"]["requirements"][0]["gate_verdict"], "conditional_go")

    def test_gate_verdict_no_go_for_low_alignment(self) -> None:
        items = [
            NormalizedItem(
                id="audit-no-go",
                kind="audit_evidence",
                source_name="audit_fixture",
                url="fixture://audit/no-go",
                title="問題のある要件",
                summary="implementation_alignmentがlow。",
                metadata={
                    "requirement_id": "REQ-NOGO",
                    "original_text": "問題のある要件。",
                    "source_type": "complaints",
                    "source_tier": "user_signal",
                    "locale": "ja-JP",
                    "kano_type": "attractive",
                    "confidence": 0.45,
                    "testability": "low",
                    "implementation_alignment": "low",
                },
            )
        ]

        artifacts = build_audit_artifacts(items, {"audit_topic": "Test"}, "run-1")
        self.assertEqual(artifacts["requirements_audit_packet"]["requirements"][0]["gate_verdict"], "no_go")

    def test_gate_summary_counts_verdicts(self) -> None:
        items = [
            NormalizedItem(
                id="audit-1",
                kind="audit_evidence",
                source_name="audit_fixture",
                url="fixture://audit/1",
                title="要件1",
                summary="go要件。",
                metadata={
                    "requirement_id": "REQ-1",
                    "original_text": "要件1",
                    "kano_type": "must_be",
                    "confidence": 0.9,
                    "testability": "high",
                    "implementation_alignment": "high",
                },
            ),
            NormalizedItem(
                id="audit-2",
                kind="audit_evidence",
                source_name="audit_fixture",
                url="fixture://audit/2",
                title="要件2",
                summary="conditional要件。",
                metadata={
                    "requirement_id": "REQ-2",
                    "original_text": "要件2",
                    "kano_type": "must_be",
                    "confidence": 0.7,
                    "testability": "medium",
                    "implementation_alignment": "medium",
                },
            ),
            NormalizedItem(
                id="audit-3",
                kind="audit_evidence",
                source_name="audit_fixture",
                url="fixture://audit/3",
                title="要件3",
                summary="no_go要件。",
                metadata={
                    "requirement_id": "REQ-3",
                    "original_text": "要件3",
                    "kano_type": "reverse",
                    "confidence": 0.6,
                    "testability": "blocked",
                    "implementation_alignment": "unknown",
                },
            ),
        ]

        artifacts = build_audit_artifacts(items, {"audit_topic": "Test"}, "run-1")
        gate_summary = artifacts["requirements_audit_packet"]["gate_summary"]

        self.assertEqual(gate_summary["go"], 1)
        self.assertEqual(gate_summary["conditional_go"], 1)
        self.assertEqual(gate_summary["no_go"], 1)
        self.assertEqual(gate_summary["total"], 3)
        self.assertIn("overall_assessment", gate_summary)
        self.assertIn("overall_reason", gate_summary)


if __name__ == "__main__":
    unittest.main()
