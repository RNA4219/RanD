from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rand_research.models import SCHEMA_VERSION


REQUIRED_FIELDS: dict[str, list[str]] = {
    "report": ["schema_version", "status", "status_reason", "state_context", "artifacts", "dependency_health"],
    "state_context": ["schema_version", "before", "after"],
    "memx_journal": ["schema_version", "entries"],
    "tracker_sync": ["schema_version", "events"],
    "kano": ["schema_version", "mode", "request_id", "topic", "persona_modes", "source_summary", "kano_candidates"],
    "requirements_packet": [
        "schema_version",
        "packet_id",
        "derived_from",
        "qeg_policy_hash_ref",
        "product_context",
        "requirements",
        "release_readiness_prelude",
    ],
    "requirements_audit_packet": ["schema_version", "document_id", "summary", "requirements", "gate_summary", "source_refs", "assumptions"],
    "downstream_handoff": [
        "schema_version",
        "handoff_id",
        "mode",
        "workflow_cookbook",
        "manual_bb_test_harness",
        "code_to_gate",
        "tracker_bridge",
        "status",
        "delivery",
        "error",
    ],
    "operations_state": ["schema_version", "dedupe_keys", "notifications", "replays"],
    "pilot_snapshot": ["schema_version", "snapshot_id", "type", "captured_at", "status", "pilot_check", "outbox_plan", "metrics", "review_required"],
    "pilot_review": ["schema_version", "review_id", "type", "reviewed_at", "reviewer", "decision", "snapshot_ref", "required_followups", "review_required"],
}


def infer_artifact_type(path: Path) -> str:
    name = path.name.removesuffix(".json")
    if name == "report":
        return "report"
    if name == "state_context":
        return "state_context"
    if name == "memx_journal":
        return "memx_journal"
    if name == "tracker_sync":
        return "tracker_sync"
    if name == "kano":
        return "kano"
    if name == "requirements_packet":
        return "requirements_packet"
    if name == "requirements_audit_packet":
        return "requirements_audit_packet"
    if name == "downstream_handoff":
        return "downstream_handoff"
    if name == "operations-state":
        return "operations_state"
    if name.endswith(".review") or name.startswith("pilot-review"):
        return "pilot_review"
    if name.startswith("pilot-snapshot"):
        return "pilot_snapshot"
    return "unknown"


def validate_artifact_payload(payload: dict[str, Any], artifact_type: str) -> dict[str, Any]:
    required = REQUIRED_FIELDS.get(artifact_type)
    issues: list[dict[str, str]] = []
    if required is None:
        issues.append({"level": "error", "message": f"unknown artifact type: {artifact_type}"})
    else:
        for field in required:
            if field not in payload:
                issues.append({"level": "error", "message": f"missing required field: {field}"})
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append({"level": "error", "message": f"schema_version must be {SCHEMA_VERSION}"})
    if artifact_type == "requirements_packet":
        _validate_requirements_packet_policy(payload, issues)
        _validate_requirements_packet_ids(payload, issues)
    if artifact_type == "downstream_handoff":
        _validate_downstream_handoff(payload, issues)
    _validate_nested_schema_versions(payload, artifact_type, issues)
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": artifact_type,
        "status": "ok" if not issues else "failed",
        "issues": issues,
    }


def validate_artifact_path(path: Path, artifact_type: str | None = None) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    detected_type = artifact_type or infer_artifact_type(path)
    result = validate_artifact_payload(payload, detected_type)
    result["path"] = str(path)
    return result


def _validate_nested_schema_versions(payload: dict[str, Any], artifact_type: str, issues: list[dict[str, str]]) -> None:
    if artifact_type == "memx_journal":
        for index, entry in enumerate(payload.get("entries", [])):
            if isinstance(entry, dict) and entry.get("schema_version") != SCHEMA_VERSION:
                issues.append({"level": "error", "message": f"entries[{index}].schema_version must be {SCHEMA_VERSION}"})
    if artifact_type == "tracker_sync":
        for index, event in enumerate(payload.get("events", [])):
            if isinstance(event, dict) and event.get("schema_version") != SCHEMA_VERSION:
                issues.append({"level": "error", "message": f"events[{index}].schema_version must be {SCHEMA_VERSION}"})


def _validate_requirements_packet_policy(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    if "qeg_policy_hash_ref" not in payload:
        issues.append({"level": "error", "message": "missing required field: qeg_policy_hash_ref"})
    for index, requirement in enumerate(payload.get("requirements", [])):
        if not isinstance(requirement, dict):
            continue
        if "gate_policy" in requirement:
            issues.append({"level": "error", "message": f"requirements[{index}].gate_policy is deprecated; use gate_policy_proposal"})
        if "gate_policy_proposal" not in requirement:
            issues.append({"level": "error", "message": f"requirements[{index}].gate_policy_proposal is required"})


def _validate_requirements_packet_ids(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    if not _is_rand_id(payload.get("packet_id")):
        issues.append({"level": "error", "message": "packet_id must use rand: prefix"})
    for index, requirement in enumerate(payload.get("requirements", [])):
        if not isinstance(requirement, dict):
            continue
        if not _is_rand_id(requirement.get("requirement_id")):
            issues.append({"level": "error", "message": f"requirements[{index}].requirement_id must use rand: prefix"})


def _validate_downstream_handoff(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    if not _is_rand_id(payload.get("handoff_id")):
        issues.append({"level": "error", "message": "handoff_id must use rand: prefix"})
    if payload.get("status") not in {"dry_run", "shadow", "live"}:
        issues.append({"level": "error", "message": "status must be one of dry_run, shadow, live"})
    delivery = payload.get("delivery")
    if not isinstance(delivery, dict):
        issues.append({"level": "error", "message": "delivery must be an object"})
        return
    if delivery.get("mode") != payload.get("status"):
        issues.append({"level": "error", "message": "delivery.mode must match status"})


def _is_rand_id(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("rand:")
