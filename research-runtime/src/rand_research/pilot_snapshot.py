from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rand_research.io_utils import atomic_write_text
from rand_research.metrics import collect_metrics
from rand_research.models import SCHEMA_VERSION
from rand_research.operations import build_outbox_plan
from rand_research.pilot_health import evaluate_pilot_readiness


def build_pilot_snapshot(runtime_root: Path, outbox_limit: int = 20) -> dict[str, Any]:
    captured_at = _now()
    pilot_check = evaluate_pilot_readiness(runtime_root)
    outbox_plan = build_outbox_plan(runtime_root / "state" / "operations-state.json", outbox_limit)
    metrics = collect_metrics(runtime_root)
    return {
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": _snapshot_id(captured_at),
        "type": "pilot_snapshot",
        "captured_at": captured_at,
        "status": pilot_check.get("status", "no_go"),
        "latest_run_id": pilot_check.get("latest_run_id"),
        "pilot_check": pilot_check,
        "outbox_plan": outbox_plan,
        "metrics": metrics,
        "review_required": pilot_check.get("status") != "go" or outbox_plan.get("pending_count", 0) > 0,
    }


def write_pilot_snapshot(runtime_root: Path, output_path: Path | None = None, outbox_limit: int = 20) -> dict[str, Any]:
    snapshot = build_pilot_snapshot(runtime_root, outbox_limit)
    target = output_path or _default_snapshot_path(runtime_root, snapshot["snapshot_id"])
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(target, json.dumps(snapshot, ensure_ascii=False, indent=2))
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "written",
        "path": str(target),
        "snapshot": snapshot,
    }


def review_pilot_snapshot(
    snapshot_path: Path,
    decision: str,
    reviewer: str,
    notes: str = "",
    output_path: Path | None = None,
) -> dict[str, Any]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    review = build_pilot_review(snapshot, snapshot_path, decision, reviewer, notes)
    target = output_path or snapshot_path.with_suffix(".review.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(target, json.dumps(review, ensure_ascii=False, indent=2))
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "written",
        "path": str(target),
        "review": review,
    }


def accept_current_pilot_state(
    runtime_root: Path,
    decision: str = "accept_with_review",
    reviewer: str = "local-operator",
    notes: str = "",
    outbox_limit: int = 20,
) -> dict[str, Any]:
    snapshot_result = write_pilot_snapshot(runtime_root, outbox_limit=outbox_limit)
    review_result = review_pilot_snapshot(
        Path(snapshot_result["path"]),
        decision,
        reviewer,
        notes,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "written",
        "snapshot_path": snapshot_result["path"],
        "review_path": review_result["path"],
        "snapshot_status": snapshot_result["snapshot"].get("status"),
        "decision": review_result["review"].get("decision"),
        "review_required": review_result["review"].get("review_required"),
        "required_followup_count": len(review_result["review"].get("required_followups", [])),
        "snapshot": snapshot_result["snapshot"],
        "review": review_result["review"],
    }


def build_pilot_review(
    snapshot: dict[str, Any],
    snapshot_path: Path,
    decision: str,
    reviewer: str,
    notes: str = "",
) -> dict[str, Any]:
    if decision not in {"accept", "accept_with_review", "hold", "block"}:
        raise ValueError(f"unsupported pilot review decision: {decision}")
    return {
        "schema_version": SCHEMA_VERSION,
        "review_id": f"pilot-review-{snapshot.get('snapshot_id', 'unknown')}",
        "type": "pilot_review",
        "reviewed_at": _now(),
        "reviewer": reviewer,
        "decision": decision,
        "notes": notes,
        "snapshot_ref": {
            "path": str(snapshot_path),
            "snapshot_id": snapshot.get("snapshot_id"),
            "status": snapshot.get("status"),
            "latest_run_id": snapshot.get("latest_run_id"),
        },
        "required_followups": _required_followups(snapshot),
        "review_required": decision in {"accept_with_review", "hold", "block"},
    }


def _required_followups(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    followups: list[dict[str, Any]] = []
    for check in snapshot.get("pilot_check", {}).get("checks", []):
        if check.get("level") == "ok":
            continue
        followups.append(
            {
                "source": "pilot_check",
                "name": check.get("name"),
                "level": check.get("level"),
                "message": check.get("message"),
                "detail": check.get("detail", {}),
            }
        )
    for action in snapshot.get("outbox_plan", {}).get("actions", []):
        followups.append(
            {
                "source": "outbox_plan",
                "name": action.get("notification_id"),
                "level": "warn",
                "message": action.get("reason"),
                "detail": {
                    "recommended_action": action.get("recommended_action"),
                    "next_commands": action.get("next_commands", []),
                },
            }
        )
    return followups


def _default_snapshot_path(runtime_root: Path, snapshot_id: str) -> Path:
    return runtime_root / "state" / "pilot-snapshots" / f"{snapshot_id}.json"


def _snapshot_id(captured_at: str) -> str:
    compact = captured_at.replace("-", "").replace(":", "").replace("+", "").replace(".", "-")
    return f"pilot-snapshot-{compact}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
