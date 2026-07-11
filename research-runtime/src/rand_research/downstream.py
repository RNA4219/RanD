from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from rand_research.artifact_schema import build_artifact_envelope, validate_artifact_payload
from rand_research.models import SCHEMA_VERSION

HandoffMode = str
DownstreamTransport = Any

VALID_HANDOFF_MODES = {"dry_run", "shadow", "live"}


def build_downstream_handoff(
    extra_payloads: dict[str, dict[str, Any]],
    run_id: str,
    mode: HandoffMode = "dry_run",
    transport: DownstreamTransport | None = None,
) -> dict[str, Any] | None:
    packet = extra_payloads.get("requirements_packet")
    audit_packet = extra_payloads.get("requirements_audit_packet")
    if not packet and not audit_packet:
        return None
    handoff_mode = mode if mode in VALID_HANDOFF_MODES else "dry_run"

    handoff = {
        "schema_version": SCHEMA_VERSION,
        "handoff_id": _rand_id(f"downstream-{run_id}"),
        "mode": "requirements_packet" if packet else "requirements_audit_packet",
        "workflow_cookbook": _task_seed_handoff(packet, audit_packet),
        "manual_bb_test_harness": _manual_bb_handoff(packet, audit_packet),
        "code_to_gate": _code_to_gate_handoff(packet, audit_packet),
        "tracker_bridge": _tracker_handoff(packet, audit_packet),
        "status": handoff_mode,
        "delivery": _delivery_observation(handoff_mode),
        "error": None,
    }
    handoff = build_artifact_envelope(
        handoff,
        artifact_id=f"rand:artifact:{run_id}:downstream_handoff",
        artifact_type="downstream_handoff",
        created_at=datetime.now(timezone.utc).isoformat(),
        input_refs=[
            str(value)
            for value in (
                (packet or {}).get("packet_id"),
                (audit_packet or {}).get("document_id"),
            )
            if value
        ],
        source_refs=list(
            (packet or audit_packet or {}).get("source_refs", [])
        ),
        downstream_allowed_uses=["review", "tracker_issue_creation"],
    )
    validation = validate_artifact_payload(handoff, "downstream_handoff")
    if validation["status"] != "ok":
        raise ValueError(f"downstream handoff validation failed: {validation['issues']}")
    handoff["delivery"] = _apply_delivery_mode(handoff, handoff_mode, transport)
    return handoff


def _rand_id(local_id: str) -> str:
    return local_id if local_id.startswith("rand:") else f"rand:{local_id}"


def _delivery_observation(mode: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "attempted": False,
        "sent": False,
        "success": None,
        "destination": "tracker_bridge",
        "destination_verdict": None,
        "error": None,
    }


def _apply_delivery_mode(
    handoff: dict[str, Any],
    mode: str,
    transport: DownstreamTransport | None,
) -> dict[str, Any]:
    observation = _delivery_observation(mode)
    if mode == "dry_run":
        observation["recorded"] = False
        return observation
    if mode == "shadow":
        observation["recorded"] = True
        observation["shadow_artifact"] = "downstream_handoff.json"
        return observation

    observation["attempted"] = True
    if transport is None:
        observation["success"] = False
        observation["error"] = "live mode requires an explicit downstream transport"
        return observation

    try:
        result = transport(handoff)
    except Exception as exc:
        observation["success"] = False
        observation["error"] = str(exc)
        return observation

    observation["sent"] = bool(result.get("sent", False))
    observation["success"] = bool(result.get("success", observation["sent"]))
    observation["destination_verdict"] = result.get("destination_verdict")
    observation["accepted_by"] = result.get("accepted_by")
    observation["response_ref"] = result.get("response_ref")
    observation["error"] = result.get("error")
    for key in (
        "attempted",
        "applied",
        "skipped",
        "failed",
        "remote_refs",
        "sync_event_refs",
        "results",
    ):
        if key in result:
            observation[key] = result[key]
    return observation


def _task_seed_handoff(packet: dict[str, Any] | None, audit_packet: dict[str, Any] | None) -> dict[str, Any]:
    if packet:
        return {
            "artifact_type": "task_seed_candidates",
            "items": [
                {
                    "title": requirement.get("title") or requirement.get("requirement_id"),
                    "objective": requirement.get("statement", ""),
                    "priority": requirement.get("priority", "P3"),
                    "acceptance": requirement.get("acceptance_criteria", []),
                    "evidence_refs": requirement.get("evidence_refs", []),
                    "risks": requirement.get("risks", []),
                }
                for requirement in packet.get("requirements", [])
            ],
        }
    return {
        "artifact_type": "audit_follow_up_tasks",
        "items": [
            {
                "title": requirement.get("requirement_id"),
                "objective": requirement.get("suggested_action", ""),
                "priority": "P1" if requirement.get("gate_verdict") == "no_go" else "P2",
                "acceptance": [f"gate_verdict becomes go or accepted residual risk: {requirement.get('gate_verdict')}"],
                "evidence_refs": [evidence.get("evidence_id") for evidence in requirement.get("evidence", [])],
                "risks": requirement.get("risks", []),
            }
            for requirement in (audit_packet or {}).get("requirements", [])
        ],
    }


def _manual_bb_handoff(packet: dict[str, Any] | None, audit_packet: dict[str, Any] | None) -> dict[str, Any]:
    if packet:
        return {
            "artifact_type": "manual_test_model_seed",
            "requirements": [
                {
                    "requirement_id": requirement.get("requirement_id"),
                    "statement": requirement.get("statement"),
                    "focus": requirement.get("manual_bb_focus", []),
                    "acceptance_criteria": requirement.get("acceptance_criteria", []),
                    "risks": requirement.get("risks", []),
                }
                for requirement in packet.get("requirements", [])
            ],
        }
    return {
        "artifact_type": "requirements_audit_testability",
        "requirements": [
            {
                "requirement_id": requirement.get("requirement_id"),
                "testability": requirement.get("testability"),
                "issues": requirement.get("issues", []),
                "suggested_action": requirement.get("suggested_action"),
            }
            for requirement in (audit_packet or {}).get("requirements", [])
        ],
    }


def _code_to_gate_handoff(packet: dict[str, Any] | None, audit_packet: dict[str, Any] | None) -> dict[str, Any]:
    if packet:
        return {
            "artifact_type": "phase_contract_seed",
            "contracts": [
                {
                    "requirement_id": requirement.get("requirement_id"),
                    "gate_policy_proposal": requirement.get("gate_policy_proposal"),
                    "qeg_policy_hash_ref": requirement.get("gate_policy_proposal", {}).get("policyHashRef"),
                    "kpi": requirement.get("kpi", []),
                    "risks": requirement.get("risks", []),
                    "kill_condition": requirement.get("kill_condition"),
                }
                for requirement in packet.get("requirements", [])
            ],
        }
    return {
        "artifact_type": "implementation_alignment_audit",
        "contracts": [
            {
                "requirement_id": requirement.get("requirement_id"),
                "implementation_alignment": requirement.get("implementation_alignment"),
                "gate_verdict": requirement.get("gate_verdict"),
                "risks": requirement.get("risks", []),
            }
            for requirement in (audit_packet or {}).get("requirements", [])
        ],
    }


def _tracker_handoff(packet: dict[str, Any] | None, audit_packet: dict[str, Any] | None) -> dict[str, Any]:
    source_items = packet.get("requirements", []) if packet else (audit_packet or {}).get("requirements", [])
    return {
        "artifact_type": "tracker_dry_run_issues",
        "issues": [
            {
                "handoff_item_id": _handoff_item_id(item),
                "title": _issue_title(item),
                "body": _issue_body(item),
                "labels": _issue_labels(item),
            }
            for item in source_items
        ],
    }


def _handoff_item_id(item: dict[str, Any]) -> str:
    identity = item.get("requirement_id")
    if not identity:
        identity = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(str(identity).encode("utf-8")).hexdigest()[:24]
    return f"rand:handoff-item:{digest}"

def _issue_title(item: dict[str, Any]) -> str:
    return item.get("title") or item.get("requirement_id") or "RanD requirement handoff"


def _issue_body(item: dict[str, Any]) -> str:
    lines = [
        f"Requirement: {item.get('requirement_id', 'unknown')}",
        "",
        item.get("statement") or item.get("original_text") or "",
        "",
        f"Gate Proposal: {_policy_proposal_label(item) or item.get('gate_verdict') or 'n/a'}",
        f"Confidence: {item.get('confidence', 'n/a')}",
    ]
    return "\n".join(lines).strip()


def _issue_labels(item: dict[str, Any]) -> list[str]:
    labels = ["rand", "requirements"]
    if item.get("kano_type"):
        labels.append(f"kano:{item['kano_type']}")
    if item.get("gate_verdict"):
        labels.append(f"gate:{item['gate_verdict']}")
    return labels


def _policy_proposal_label(item: dict[str, Any]) -> str | None:
    proposal = item.get("gate_policy_proposal")
    if isinstance(proposal, dict):
        return proposal.get("proposal")
    if isinstance(proposal, str):
        return proposal
    return None
