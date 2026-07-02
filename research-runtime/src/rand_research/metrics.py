from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from rand_research.models import SCHEMA_VERSION


def collect_metrics(runtime_root: Path) -> dict[str, Any]:
    runs_root = runtime_root / "runs"
    reports = _load_reports(runs_root)
    operations = _load_json(runtime_root / "state" / "operations-state.json", {})
    tracker = _load_json(runtime_root / "state" / "tracker-sync.json", {"events": []})

    by_status = Counter(report.get("status", "unknown") for report in reports)
    by_day = Counter(_day(report.get("run_meta", {}).get("started_at")) for report in reports)
    reasons = Counter(reason for report in reports for reason in report.get("status_reason", []))

    notifications = operations.get("notifications", [])
    replays = operations.get("replays", [])
    tracker_events = tracker.get("events", [])
    handoffs = _load_downstream_handoffs(runs_root)
    handoff_delivery = [handoff.get("delivery", {}) for handoff in handoffs]
    handoff_modes = Counter(handoff.get("status", "unknown") for handoff in handoffs)
    destination_verdicts = Counter(
        delivery.get("destination_verdict")
        for delivery in handoff_delivery
        if delivery.get("destination_verdict")
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "run_count": len(reports),
        "daily_run_count": dict(sorted(by_day.items())),
        "status_counts": dict(sorted(by_status.items())),
        "status_reason_counts": dict(sorted(reasons.items())),
        "report_save_failed_count": reasons.get("report_save_failed", 0),
        "state_write_failed_count": reasons.get("state_write_failed", 0),
        "replay_count": len(replays),
        "pending_notification_count": sum(1 for item in notifications if item.get("status") in {"pending", "failed"}),
        "notification_failure_count": sum(1 for item in notifications if item.get("status") == "failed"),
        "tracker_sync_failure_count": sum(1 for item in tracker_events if item.get("status") not in {"ok", None}),
        "duplicate_suppression_count": sum(1 for item in notifications if item.get("status") == "duplicate_suppressed"),
        "downstream_handoff_count": len(handoffs),
        "downstream_handoff_mode_counts": dict(sorted(handoff_modes.items())),
        "downstream_handoff_live_success_count": sum(
            1 for delivery in handoff_delivery if delivery.get("mode") == "live" and delivery.get("success") is True
        ),
        "downstream_handoff_live_failure_count": sum(
            1 for delivery in handoff_delivery if delivery.get("mode") == "live" and delivery.get("success") is False
        ),
        "downstream_handoff_destination_verdict_counts": dict(sorted(destination_verdicts.items())),
    }


def _load_reports(runs_root: Path) -> list[dict[str, Any]]:
    if not runs_root.exists():
        return []
    reports: list[dict[str, Any]] = []
    for path in sorted(runs_root.glob("*/report.json")):
        try:
            reports.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return reports


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _load_downstream_handoffs(runs_root: Path) -> list[dict[str, Any]]:
    if not runs_root.exists():
        return []
    handoffs: list[dict[str, Any]] = []
    for path in sorted(runs_root.glob("*/downstream_handoff.json")):
        try:
            handoffs.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return handoffs


def _day(value: str | None) -> str:
    return (value or "unknown")[:10]
