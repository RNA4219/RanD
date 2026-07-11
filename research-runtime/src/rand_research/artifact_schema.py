from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from rand_research.models import SCHEMA_VERSION

ARTIFACT_SCHEMA_VERSION = "2.0"
PRODUCER_VERSION = "0.3.0"

LEGACY_REQUIRED_FIELDS: dict[str, list[str]] = {
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
    "requirements_audit_packet": [
        "schema_version",
        "document_id",
        "summary",
        "requirements",
        "gate_summary",
        "source_refs",
        "assumptions",
    ],
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
    "pilot_snapshot": [
        "schema_version",
        "snapshot_id",
        "type",
        "captured_at",
        "status",
        "pilot_check",
        "outbox_plan",
        "metrics",
        "review_required",
    ],
    "pilot_review": [
        "schema_version",
        "review_id",
        "type",
        "reviewed_at",
        "reviewer",
        "decision",
        "snapshot_ref",
        "required_followups",
        "review_required",
    ],
}


def artifact_schema() -> dict[str, Any]:
    resource = Path(__file__).resolve().parent / "schemas" / "artifact-2.0.schema.json"
    return json.loads(resource.read_text(encoding="utf-8"))


_VALIDATOR = Draft202012Validator(artifact_schema(), format_checker=FormatChecker())


def build_artifact_envelope(
    payload: dict[str, Any],
    *,
    artifact_id: str,
    artifact_type: str,
    created_at: str | None = None,
    input_refs: list[str] | None = None,
    source_refs: list[str] | None = None,
    downstream_allowed_uses: list[str] | None = None,
) -> dict[str, Any]:
    status = str(payload.get("status", "ok"))
    result = dict(payload)
    result.update(
        {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "id": artifact_id,
            "type": artifact_type,
            "producer": {"name": "RanD", "version": PRODUCER_VERSION},
            "created_at": created_at or datetime.now(timezone.utc).isoformat(),
            "input_refs": list(input_refs or payload.get("input_refs", [])),
            "source_refs": list(source_refs or payload.get("source_refs", [])),
            "status": status,
            "assumptions": list(payload.get("assumptions", [])),
            "limitations": list(payload.get("limitations", [])),
            "review_required": bool(
                payload.get("review_required", status in {"degraded", "failed", "needs_review"})
            ),
            "downstream_allowed_uses": list(
                downstream_allowed_uses
                or payload.get("downstream_allowed_uses", ["review", "analysis"])
            ),
        }
    )
    return result


def infer_artifact_type(path: Path) -> str:
    name = path.name.removesuffix(".json")
    aliases = {
        "report": "report",
        "state_context": "state_context",
        "memx_journal": "memx_journal",
        "tracker_sync": "tracker_sync",
        "kano": "kano",
        "requirements_packet": "requirements_packet",
        "requirements_audit_packet": "requirements_audit_packet",
        "downstream_handoff": "downstream_handoff",
        "operations-state": "operations_state",
        "manifest": "manifest",
    }
    if name in aliases:
        return aliases[name]
    if name.endswith(".review") or name.startswith("pilot-review"):
        return "pilot_review"
    if name.startswith("pilot-snapshot"):
        return "pilot_snapshot"
    return "unknown"


def validate_artifact_payload(payload: dict[str, Any], artifact_type: str) -> dict[str, Any]:
    version = payload.get("schema_version")
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    legacy = version == SCHEMA_VERSION

    if legacy:
        _validate_legacy(payload, artifact_type, issues)
        warnings.append(
            {
                "level": "warning",
                "message": "legacy artifact schema 1.0 is read-only compatible; regenerate as 2.0",
            }
        )
    elif version == ARTIFACT_SCHEMA_VERSION:
        for error in sorted(_VALIDATOR.iter_errors(payload), key=lambda item: list(item.path)):
            location = ".".join(str(part) for part in error.absolute_path)
            prefix = f"{location}: " if location else ""
            issues.append({"level": "error", "message": prefix + error.message})
        created_at = payload.get("created_at")
        if isinstance(created_at, str):
            try:
                parsed_created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                if parsed_created_at.tzinfo is None or parsed_created_at.utcoffset() is None:
                    raise ValueError("timezone is required")
            except ValueError:
                issues.append(
                    {
                        "level": "error",
                        "message": "created_at must be a timezone-aware date-time",
                    }
                )
        if payload.get("type") != artifact_type:
            issues.append(
                {
                    "level": "error",
                    "message": f"type must match artifact type {artifact_type}",
                }
            )
        _validate_type_specific(payload, artifact_type, issues)
    else:
        issues.append(
            {
                "level": "error",
                "message": (
                    f"schema_version must be {ARTIFACT_SCHEMA_VERSION}; "
                    f"{SCHEMA_VERSION} is the only supported legacy version"
                ),
            }
        )

    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_type": artifact_type,
        "artifact_schema_version": version,
        "status": "ok" if not issues else "failed",
        "legacy": legacy,
        "issues": issues,
        "warnings": warnings,
    }


def validate_artifact_path(path: Path, artifact_type: str | None = None) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    detected_type = artifact_type or infer_artifact_type(path)
    result = validate_artifact_payload(payload, detected_type)
    if detected_type == "manifest" and result["status"] == "ok":
        checksum_issues = validate_manifest_checksums(payload, path.parent)
        result["issues"].extend(checksum_issues)
        if checksum_issues:
            result["status"] = "failed"
    result["path"] = str(path)
    return result


def validate_manifest_checksums(
    manifest: dict[str, Any],
    artifact_root: Path,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for index, entry in enumerate(manifest.get("artifacts", [])):
        if not isinstance(entry, dict):
            issues.append({"level": "error", "message": f"artifacts[{index}] must be an object"})
            continue
        target = artifact_root / Path(str(entry.get("path", ""))).name
        try:
            content = target.read_bytes()
        except OSError as exc:
            issues.append(
                {
                    "level": "error",
                    "message": f"artifacts[{index}] cannot be read: {exc}",
                }
            )
            continue
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != entry.get("sha256"):
            issues.append(
                {
                    "level": "error",
                    "message": f"artifacts[{index}].sha256 mismatch",
                }
            )
        if len(content) != entry.get("size_bytes"):
            issues.append(
                {
                    "level": "error",
                    "message": f"artifacts[{index}].size_bytes mismatch",
                }
            )
    return issues


def _validate_legacy(
    payload: dict[str, Any],
    artifact_type: str,
    issues: list[dict[str, str]],
) -> None:
    required = LEGACY_REQUIRED_FIELDS.get(artifact_type)
    if required is None:
        issues.append({"level": "error", "message": f"unknown artifact type: {artifact_type}"})
        return
    for field in required:
        if field not in payload:
            issues.append({"level": "error", "message": f"missing required field: {field}"})
    if artifact_type == "memx_journal":
        for index, entry in enumerate(payload.get("entries", [])):
            if isinstance(entry, dict) and entry.get("schema_version") != SCHEMA_VERSION:
                issues.append(
                    {
                        "level": "error",
                        "message": f"entries[{index}].schema_version must be {SCHEMA_VERSION}",
                    }
                )
    if artifact_type == "tracker_sync":
        for index, event in enumerate(payload.get("events", [])):
            if isinstance(event, dict) and event.get("schema_version") != SCHEMA_VERSION:
                issues.append(
                    {
                        "level": "error",
                        "message": f"events[{index}].schema_version must be {SCHEMA_VERSION}",
                    }
                )
    _validate_type_specific(payload, artifact_type, issues)


def _validate_type_specific(
    payload: dict[str, Any],
    artifact_type: str,
    issues: list[dict[str, str]],
) -> None:
    if artifact_type == "requirements_packet":
        _validate_requirements_packet_policy(payload, issues)
        _validate_requirements_packet_ids(payload, issues)
    if artifact_type == "downstream_handoff":
        _validate_downstream_handoff(payload, issues)


def _validate_requirements_packet_policy(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    if "qeg_policy_hash_ref" not in payload:
        issues.append({"level": "error", "message": "missing required field: qeg_policy_hash_ref"})
    for index, requirement in enumerate(payload.get("requirements", [])):
        if not isinstance(requirement, dict):
            continue
        if "gate_policy" in requirement:
            issues.append(
                {
                    "level": "error",
                    "message": f"requirements[{index}].gate_policy is deprecated; use gate_policy_proposal",
                }
            )
        if "gate_policy_proposal" not in requirement:
            issues.append(
                {
                    "level": "error",
                    "message": f"requirements[{index}].gate_policy_proposal is required",
                }
            )


def _validate_requirements_packet_ids(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    if not _is_rand_id(payload.get("packet_id")):
        issues.append({"level": "error", "message": "packet_id must use rand: prefix"})
    for index, requirement in enumerate(payload.get("requirements", [])):
        if isinstance(requirement, dict) and not _is_rand_id(requirement.get("requirement_id")):
            issues.append(
                {
                    "level": "error",
                    "message": f"requirements[{index}].requirement_id must use rand: prefix",
                }
            )


def _validate_downstream_handoff(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    if not _is_rand_id(payload.get("handoff_id")):
        issues.append({"level": "error", "message": "handoff_id must use rand: prefix"})
    if payload.get("status") not in {"dry_run", "shadow", "live"}:
        issues.append({"level": "error", "message": "status must be one of dry_run, shadow, live"})
    delivery = payload.get("delivery")
    if not isinstance(delivery, dict):
        issues.append({"level": "error", "message": "delivery must be an object"})
    elif delivery.get("mode") != payload.get("status"):
        issues.append({"level": "error", "message": "delivery.mode must match status"})


def _is_rand_id(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("rand:")