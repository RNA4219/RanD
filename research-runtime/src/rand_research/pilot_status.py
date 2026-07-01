from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rand_research.models import SCHEMA_VERSION
from rand_research.operations import build_outbox_plan
from rand_research.pilot_health import evaluate_pilot_readiness


def build_pilot_status(runtime_root: Path, outbox_limit: int = 20) -> dict[str, Any]:
    readiness = evaluate_pilot_readiness(runtime_root)
    outbox_plan = build_outbox_plan(runtime_root / "state" / "operations-state.json", outbox_limit)
    latest_snapshot = _latest_path(runtime_root / "state" / "pilot-snapshots", "*.json", exclude_suffix=".review.json")
    latest_review = _latest_path(runtime_root / "state" / "pilot-snapshots", "*.review.json")
    review_state = _review_state(latest_snapshot, latest_review)
    next_steps = _next_steps(readiness, outbox_plan, latest_snapshot, review_state)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": readiness.get("status", "no_go"),
        "summary": readiness.get("summary", "pilot runtime status unavailable"),
        "latest_run_id": readiness.get("latest_run_id"),
        "latest_snapshot": str(latest_snapshot) if latest_snapshot else None,
        "latest_review": str(latest_review) if latest_review else None,
        "latest_review_decision": review_state.get("decision"),
        "review_covers_latest_snapshot": review_state["covers_latest_snapshot"],
        "pending_outbox_count": outbox_plan.get("pending_count", 0),
        "next_steps": next_steps,
        "readiness": readiness,
        "outbox_plan": outbox_plan,
    }


def build_pilot_status_summary(runtime_root: Path, outbox_limit: int = 20) -> dict[str, Any]:
    status = build_pilot_status(runtime_root, outbox_limit)
    next_step = status.get("next_steps", [{}])[0] if status.get("next_steps") else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status.get("status"),
        "summary": status.get("summary"),
        "latest_run_id": status.get("latest_run_id"),
        "pending_outbox_count": status.get("pending_outbox_count", 0),
        "latest_review_decision": status.get("latest_review_decision"),
        "review_covers_latest_snapshot": status.get("review_covers_latest_snapshot", False),
        "next_step": next_step.get("name"),
        "next_command": next_step.get("command"),
    }


def _next_steps(
    readiness: dict[str, Any],
    outbox_plan: dict[str, Any],
    latest_snapshot: Path | None,
    review_state: dict[str, Any],
) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = []
    pending_count = int(outbox_plan.get("pending_count", 0) or 0)
    status = readiness.get("status", "no_go")
    review_covers_pending = review_state["covers_latest_snapshot"] and review_state.get("decision") in {
        "accept",
        "accept_with_review",
    }
    if pending_count and not review_covers_pending:
        steps.append(
            {
                "name": "review_outbox",
                "reason": f"{pending_count} pending or failed notification(s) need disposition",
                "command": "python -m rand_research.cli outbox-plan",
            }
        )
    if latest_snapshot is None:
        steps.append(
            {
                "name": "capture_snapshot",
                "reason": "no pilot snapshot has been recorded",
                "command": "python -m rand_research.cli pilot-snapshot",
            }
        )
    elif not review_state["covers_latest_snapshot"]:
        steps.append(
            {
                "name": "record_review",
                "reason": "latest pilot snapshot has no current review artifact",
                "command": f"python -m rand_research.cli pilot-review --snapshot {latest_snapshot} --decision accept_with_review",
            }
        )
    if status == "no_go":
        steps.insert(
            0,
            {
                "name": "inspect_blockers",
                "reason": "pilot readiness is no_go",
                "command": "python -m rand_research.cli pilot-check",
            },
        )
    if not steps:
        if status == "degraded":
            steps.append(
                {
                    "name": "continue_pilot_with_review",
                    "reason": "pilot readiness is degraded, but the latest snapshot has an accepting review",
                    "command": "python -m rand_research.cli pilot-status",
                }
            )
            return steps
        steps.append(
            {
                "name": "continue_pilot",
                "reason": "pilot readiness is reviewed and no pending outbox remains",
                "command": "python -m rand_research.cli pilot-check",
            }
        )
    return steps


def _latest_path(root: Path, pattern: str, exclude_suffix: str | None = None) -> Path | None:
    if not root.exists():
        return None
    paths = [path for path in root.glob(pattern) if path.is_file()]
    if exclude_suffix:
        paths = [path for path in paths if not path.name.endswith(exclude_suffix)]
    return max(paths, key=lambda path: path.stat().st_mtime) if paths else None


def _review_state(latest_snapshot: Path | None, latest_review: Path | None) -> dict[str, Any]:
    if latest_snapshot is None or latest_review is None:
        return {"covers_latest_snapshot": False, "decision": None}
    try:
        snapshot = json.loads(latest_snapshot.read_text(encoding="utf-8"))
        review = json.loads(latest_review.read_text(encoding="utf-8"))
    except Exception:
        return {"covers_latest_snapshot": False, "decision": None}
    snapshot_ref = review.get("snapshot_ref", {})
    covers = snapshot_ref.get("snapshot_id") == snapshot.get("snapshot_id") or Path(
        snapshot_ref.get("path", "")
    ) == latest_snapshot
    return {
        "covers_latest_snapshot": covers,
        "decision": review.get("decision"),
    }
