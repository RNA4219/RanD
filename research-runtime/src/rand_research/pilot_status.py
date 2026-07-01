from __future__ import annotations

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
    next_steps = _next_steps(readiness, outbox_plan, latest_snapshot, latest_review)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": readiness.get("status", "no_go"),
        "summary": readiness.get("summary", "pilot runtime status unavailable"),
        "latest_run_id": readiness.get("latest_run_id"),
        "latest_snapshot": str(latest_snapshot) if latest_snapshot else None,
        "latest_review": str(latest_review) if latest_review else None,
        "pending_outbox_count": outbox_plan.get("pending_count", 0),
        "next_steps": next_steps,
        "readiness": readiness,
        "outbox_plan": outbox_plan,
    }


def _next_steps(
    readiness: dict[str, Any],
    outbox_plan: dict[str, Any],
    latest_snapshot: Path | None,
    latest_review: Path | None,
) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = []
    pending_count = int(outbox_plan.get("pending_count", 0) or 0)
    status = readiness.get("status", "no_go")
    if pending_count:
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
    elif latest_review is None or latest_review.stat().st_mtime < latest_snapshot.stat().st_mtime:
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
