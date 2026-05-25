from __future__ import annotations

from collections import Counter
from typing import Any

from rand_research.fetchers import _slugify
from rand_research.models import NormalizedItem, SCHEMA_VERSION

KANO_TYPES = {"must_be", "performance", "attractive", "indifferent", "reverse", "questionable"}

GATE_VERDICTS = {"go", "conditional_go", "no_go"}

TESTABILITY_LEVELS = {"high", "medium", "low", "blocked"}

IMPLEMENTATION_ALIGNMENT_LEVELS = {"high", "medium", "low", "unknown"}


def build_kano_artifacts(items: list[NormalizedItem], preset: dict[str, Any], run_id: str) -> dict[str, dict[str, Any]]:
    candidates = _build_candidates(items, preset, run_id)
    requirements = [_candidate_to_requirement(candidate, index) for index, candidate in enumerate(candidates, start=1) if _promotable(candidate)]
    packet = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": f"rp-{run_id}",
        "derived_from": "kano.json",
        "product_context": preset.get(
            "product_context",
            {
                "name": preset.get("name", "RanD KanoMode"),
                "domain": "requirements discovery",
                "target_segment": "unspecified",
                "locales": preset.get("locales", ["ja-JP", "en-US"]),
            },
        ),
        "assumptions": preset.get(
            "assumptions",
            [
                "live web evidence is optional for offline evaluation",
                "public user signals can be biased toward extreme opinions",
            ],
        ),
        "requirements": requirements,
        "release_readiness_prelude": {
            "status": "draft",
            "preconditions": [
                "offline eval passes",
                "human review accepts promoted requirements",
            ],
        },
    }
    kano = {
        "schema_version": SCHEMA_VERSION,
        "mode": "kano",
        "request_id": f"kano-{run_id}",
        "topic": preset.get("topic", preset.get("query_template", "RanD KanoMode requirements")),
        "persona_modes": preset.get("persona_modes", ["researcher", "user", "gatekeeper", "product"]),
        "source_summary": {
            "total_evidence": len(items),
            "primary_source_count": _count_by_tier(items, "primary"),
            "user_signal_count": _count_by_tier(items, "user_signal"),
            "comparison_source_count": _count_by_type(items, "compare"),
            "freshness_window_days": preset.get("freshness_window_days", 180),
        },
        "kano_candidates": candidates,
        "known_biases": [
            "primary sources can carry positive positioning bias",
            "public reviews can overrepresent strong negative or positive opinions",
        ],
    }
    return {"kano": kano, "requirements_packet": packet}


def _build_candidates(items: list[NormalizedItem], preset: dict[str, Any], run_id: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[NormalizedItem]] = {}
    for item in items:
        candidate_id = item.metadata.get("kano_candidate_id") or _slugify(item.title)[:40] or item.id
        grouped.setdefault(candidate_id, []).append(item)

    candidates: list[dict[str, Any]] = []
    for index, (candidate_key, group) in enumerate(sorted(grouped.items()), start=1):
        first = group[0]
        candidate_id = f"KC-{index:03d}"
        kano_type = _select_kano_type(group)
        confidence = round(sum(float(item.metadata.get("confidence", 0.6)) for item in group) / len(group), 2)
        evidence = [_evidence_entry(item, evidence_index) for evidence_index, item in enumerate(group, start=1)]
        statement = first.metadata.get("requirement_statement") or first.title
        candidates.append(
            {
                "candidate_id": candidate_id,
                "source_candidate_id": candidate_key,
                "statement": statement,
                "kano_type": kano_type,
                "confidence": confidence,
                "evidence": evidence,
                "persona_votes": _persona_votes(kano_type, preset.get("persona_modes", [])),
                "bias_note": first.metadata.get("bias_note", ""),
                "kill_condition": first.metadata.get("kill_condition", ""),
                "open_questions": first.metadata.get("open_questions", []),
                "derived_from_run": run_id,
            }
        )
    return candidates


def _candidate_to_requirement(candidate: dict[str, Any], index: int) -> dict[str, Any]:
    kano_type = candidate["kano_type"]
    return {
        "requirement_id": f"REQ-{index:03d}",
        "title": candidate["statement"][:80],
        "statement": candidate["statement"],
        "kano_type": kano_type,
        "priority": _priority_for(kano_type),
        "confidence": candidate["confidence"],
        "evidence_refs": [candidate["candidate_id"], *[entry["evidence_id"] for entry in candidate.get("evidence", [])]],
        "kpi": _kpi_for(kano_type),
        "acceptance_criteria": _acceptance_for(kano_type),
        "risks": _risks_for(kano_type),
        "manual_bb_focus": ["evidence absence", "conflicting evidence", "locale-specific expectation"],
        "downstream_hooks": {
            "workflow_cookbook": "task_seed_and_evidence",
            "manual_bb_test_harness": "feature_spec_and_test_model",
            "code_to_gate": "phase_contract_or_intake",
            "shipyard_cp": "plan_stage_task",
        },
        "gate_policy": _gate_policy_for(kano_type),
        "bias_note": candidate["bias_note"],
        "kill_condition": candidate["kill_condition"],
    }


def _evidence_entry(item: NormalizedItem, index: int) -> dict[str, Any]:
    return {
        "evidence_id": f"EV-{index:03d}-{item.id[:24]}",
        "source_type": item.metadata.get("source_type", item.kind),
        "source_tier": item.metadata.get("source_tier", "unknown"),
        "source_ref": item.url,
        "summary": item.summary or item.title,
        "weight": float(item.metadata.get("weight", item.metadata.get("confidence", 0.6))),
        "freshness_days": item.metadata.get("freshness_days"),
        "locale": item.metadata.get("locale", "und"),
    }


def _select_kano_type(items: list[NormalizedItem]) -> str:
    votes = [item.metadata.get("kano_type", "") for item in items]
    counts = Counter(vote for vote in votes if vote in KANO_TYPES)
    if not counts:
        return "questionable"
    return counts.most_common(1)[0][0]


def _persona_votes(kano_type: str, persona_modes: list[str]) -> dict[str, str]:
    modes = persona_modes or ["researcher", "user", "gatekeeper", "product"]
    return {mode: kano_type for mode in modes}


def _promotable(candidate: dict[str, Any]) -> bool:
    return bool(candidate.get("confidence")) and bool(candidate.get("bias_note")) and bool(candidate.get("kill_condition"))


def _count_by_tier(items: list[NormalizedItem], tier: str) -> int:
    return sum(1 for item in items if item.metadata.get("source_tier") == tier)


def _count_by_type(items: list[NormalizedItem], source_type: str) -> int:
    return sum(1 for item in items if item.metadata.get("source_type") == source_type)


def _priority_for(kano_type: str) -> str:
    return {
        "must_be": "P0",
        "performance": "P1",
        "reverse": "P1",
        "attractive": "P2",
        "indifferent": "P3",
        "questionable": "P3",
    }.get(kano_type, "P3")


def _gate_policy_for(kano_type: str) -> str:
    return {
        "must_be": "hard_gate",
        "performance": "threshold_gate",
        "attractive": "soft_experiment_gate",
        "reverse": "negative_gate",
        "indifferent": "observe_only",
        "questionable": "do_not_gate",
    }.get(kano_type, "do_not_gate")


def _kpi_for(kano_type: str) -> list[dict[str, str]]:
    if kano_type == "must_be":
        return [{"name": "failure_rate", "target": "<=0.05", "measurement": "offline eval and human review"}]
    if kano_type == "performance":
        return [{"name": "task_success_rate", "target": ">=0.80", "measurement": "pilot review"}]
    if kano_type == "attractive":
        return [{"name": "adoption_or_praise_rate", "target": "track", "measurement": "pilot review"}]
    return [{"name": "observation_count", "target": "track", "measurement": "evidence review"}]


def _acceptance_for(kano_type: str) -> list[str]:
    if kano_type == "must_be":
        return [
            "candidate has at least one direct user-signal or primary evidence reference",
            "confidence, bias_note, and kill_condition are non-empty",
        ]
    if kano_type == "attractive":
        return ["candidate remains non-blocking unless promoted by pilot evidence"]
    return ["candidate has evidence references and explicit gate policy"]


def _risks_for(kano_type: str) -> list[str]:
    if kano_type == "must_be":
        return ["complaint bias can overpromote blockers"]
    if kano_type == "attractive":
        return ["overbuilding delighters can distract from must-be gaps"]
    if kano_type == "reverse":
        return ["default enablement can lower satisfaction for some segments"]
    return ["classification can drift as expectations change"]


def build_audit_artifacts(
    items: list[NormalizedItem],
    preset: dict[str, Any],
    run_id: str,
    document_id: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Build requirements_audit_packet.json from audit evidence items."""
    audit_requirements = _build_audit_requirements(items, preset, run_id)
    gate_summary = _build_gate_summary(audit_requirements)

    audit_packet = {
        "schema_version": SCHEMA_VERSION,
        "document_id": document_id or preset.get("audit_document_id", f"AUDIT-{run_id}"),
        "summary": _audit_summary(items, audit_requirements, gate_summary),
        "requirements": audit_requirements,
        "gate_summary": gate_summary,
        "source_refs": {
            "audited_document": preset.get("audit_document_ref", ""),
            "external_evidence": [item.url for item in items if item.metadata.get("source_tier") in ("user_signal", "comparison")],
            "implementation_evidence": [item.url for item in items if item.metadata.get("source_tier") == "primary"],
        },
        "assumptions": preset.get(
            "audit_assumptions",
            [
                "audit items are representative of requirement coverage",
                "external evidence may have temporal drift",
                "implementation_alignment is inferred from available evidence",
            ],
        ),
    }

    kano = {
        "schema_version": SCHEMA_VERSION,
        "mode": "kano_audit",
        "request_id": f"kano-audit-{run_id}",
        "topic": preset.get("audit_topic", preset.get("topic", "Requirement Definition Audit")),
        "persona_modes": preset.get("persona_modes", ["researcher", "gatekeeper", "product"]),
        "source_summary": {
            "total_evidence": len(items),
            "primary_source_count": _count_by_tier(items, "primary"),
            "user_signal_count": _count_by_tier(items, "user_signal"),
            "comparison_source_count": _count_by_type(items, "compare"),
            "freshness_window_days": preset.get("freshness_window_days", 180),
        },
        "kano_candidates": [
            {
                "candidate_id": req["requirement_id"],
                "statement": req["original_text"],
                "kano_type": req["kano_estimate"],
                "confidence": req["confidence"],
                "evidence": req["evidence"],
                "persona_votes": {"gatekeeper": req["gate_verdict"]},
                "bias_note": "",
                "kill_condition": "",
            }
            for req in audit_requirements
        ],
        "known_biases": [
            "audit scope may miss undocumented requirements",
            "implementation evidence can lag behind actual code state",
        ],
    }

    return {"kano": kano, "requirements_audit_packet": audit_packet}


def _build_audit_requirements(
    items: list[NormalizedItem],
    preset: dict[str, Any],
    run_id: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[NormalizedItem]] = {}
    for item in items:
        req_id = item.metadata.get("requirement_id") or f"REQ-{item.id[:8]}"
        grouped.setdefault(req_id, []).append(item)

    requirements: list[dict[str, Any]] = []
    for req_id, group in sorted(grouped.items()):
        first = group[0]
        kano_estimate = _select_kano_type(group)
        confidence = round(sum(float(item.metadata.get("confidence", 0.6)) for item in group) / len(group), 2)
        testability = first.metadata.get("testability", "medium")
        implementation_alignment = first.metadata.get("implementation_alignment", "unknown")
        gate_verdict = _determine_gate_verdict(kano_estimate, testability, implementation_alignment, confidence)

        evidence = [
            {
                "evidence_id": f"EV-AUDIT-{idx:03d}-{item.id[:16]}",
                "source_type": item.metadata.get("source_type", item.kind),
                "source_tier": item.metadata.get("source_tier", "unknown"),
                "source_ref": item.url,
                "summary": item.summary or item.title,
                "weight": float(item.metadata.get("weight", 0.6)),
                "freshness_days": item.metadata.get("freshness_days"),
                "locale": item.metadata.get("locale", "und"),
            }
            for idx, item in enumerate(group, start=1)
        ]

        requirements.append(
            {
                "requirement_id": req_id,
                "original_text": first.metadata.get("original_text", first.title),
                "kano_estimate": kano_estimate,
                "confidence": confidence,
                "evidence": evidence,
                "testability": testability if testability in TESTABILITY_LEVELS else "medium",
                "implementation_alignment": implementation_alignment if implementation_alignment in IMPLEMENTATION_ALIGNMENT_LEVELS else "unknown",
                "risks": first.metadata.get("risks", _risks_for(kano_estimate)),
                "issues": first.metadata.get("issues", []),
                "suggested_action": first.metadata.get("suggested_action", _suggested_action_for(gate_verdict)),
                "gate_verdict": gate_verdict,
            }
        )
    return requirements


def _determine_gate_verdict(
    kano_estimate: str,
    testability: str,
    implementation_alignment: str,
    confidence: float,
) -> str:
    """Determine gate verdict based on Requirement Definition Gate criteria.

    Specification 7節:
    - go: must-be抜けが少なく、受入条件とKPIが観測可能で、実装整合に大きな破綻がない
    - conditional_go: 方向性は妥当だが、受入条件、KPI、根拠、実装リスクの補強が必要
    - no_go: must-be抜け、attractiveのmust-be誤扱い、価値根拠不足、検収不能、実装負債過大
    """
    if kano_estimate == "reverse":
        return "no_go"

    if testability == "blocked" or implementation_alignment == "low":
        return "no_go"

    if confidence < 0.5:
        return "conditional_go"

    if testability == "low" or implementation_alignment == "unknown":
        return "conditional_go"

    if kano_estimate == "attractive" and confidence < 0.7:
        return "conditional_go"

    if testability == "medium" or implementation_alignment == "medium":
        return "conditional_go"

    return "go"


def _suggested_action_for(gate_verdict: str) -> str:
    return {
        "go": "維持。既存テストでcoverage確認。",
        "conditional_go": "補強。受入条件、KPI、根拠、実装リスクの確認。",
        "no_go": "再設計。要件文改訂または削除候補。",
    }.get(gate_verdict, "確認")


def _build_gate_summary(requirements: list[dict[str, Any]]) -> dict[str, Any]:
    verdict_counts = Counter(req["gate_verdict"] for req in requirements)
    verdict_distribution: dict[str, list[str]] = {}
    for req in requirements:
        verdict = req["gate_verdict"]
        verdict_distribution.setdefault(verdict, []).append(req["requirement_id"])

    go_count = verdict_counts.get("go", 0)
    no_go_count = verdict_counts.get("no_go", 0)
    conditional_count = verdict_counts.get("conditional_go", 0)

    overall = "conditional_go" if no_go_count > 0 or conditional_count > go_count else "go" if no_go_count == 0 else "no_go"
    overall_reason = (
        f"{no_go_count}件no_goあり。要件改訂後に再監査推奨。" if no_go_count > 0
        else f"{conditional_count}件conditional_goあり。補強後に再監査推奨。" if conditional_count > 0
        else "すべてgo。維持推奨。"
    )

    return {
        "go": go_count,
        "conditional_go": conditional_count,
        "no_go": no_go_count,
        "total": len(requirements),
        "verdict_distribution": verdict_distribution,
        "overall_assessment": overall,
        "overall_reason": overall_reason,
    }


def _audit_summary(
    items: list[NormalizedItem],
    requirements: list[dict[str, Any]],
    gate_summary: dict[str, Any],
) -> str:
    return (
        f"{len(requirements)}要件監査。"
        f"go={gate_summary['go']}, conditional_go={gate_summary['conditional_go']}, no_go={gate_summary['no_go']}."
        f"{gate_summary['overall_reason']}"
    )
