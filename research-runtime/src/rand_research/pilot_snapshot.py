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


def _default_snapshot_path(runtime_root: Path, snapshot_id: str) -> Path:
    return runtime_root / "state" / "pilot-snapshots" / f"{snapshot_id}.json"


def _snapshot_id(captured_at: str) -> str:
    compact = captured_at.replace("-", "").replace(":", "").replace("+", "").replace(".", "-")
    return f"pilot-snapshot-{compact}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
