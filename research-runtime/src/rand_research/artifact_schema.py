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
    "requirements_packet": ["schema_version", "packet_id", "derived_from", "product_context", "requirements", "release_readiness_prelude"],
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
        "error",
    ],
    "operations_state": ["schema_version", "dedupe_keys", "notifications", "replays"],
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
