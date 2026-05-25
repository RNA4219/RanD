from __future__ import annotations

from collections import Counter
from typing import Any

from rand_research.fetchers import _slugify
from rand_research.models import NormalizedItem, SCHEMA_VERSION

KANO_TYPES = {"must_be", "performance", "attractive", "indifferent", "reverse", "questionable"}


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
