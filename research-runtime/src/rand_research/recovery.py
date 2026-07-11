from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rand_research.io_utils import locked_update_json
from rand_research.models import SCHEMA_VERSION


def reconcile_runtime_state(
    runs_root: Path,
    taskstate_path: Path,
    operations_path: Path,
    stale_after_seconds: float = 300.0,
) -> dict[str, list[str]]:
    committed = _committed_runs(runs_root)
    repaired_tasks: list[str] = []
    repaired_notifications: list[str] = []

    def update_tasks(payload: dict[str, Any]) -> None:
        payload.setdefault("schema_version", SCHEMA_VERSION)
        tasks = payload.setdefault("tasks", [])
        now = datetime.now(timezone.utc).isoformat()
        for run_id, run in committed.items():
            task_id = f"task-{run_id}"
            task = next((item for item in tasks if item.get("task_id") == task_id), None)
            finalized = task is not None and task.get("status") in {"done", "needs_review", "failed"}
            artifacts_match = task is not None and task.get("artifacts") == run["artifacts"]
            if finalized and artifacts_match:
                continue
            if task is None:
                task = {
                    "task_id": task_id,
                    "run_id": run_id,
                    "preset": run["preset"],
                    "created_at": now,
                }
                tasks.append(task)
            reasons = list(task.get("status_reason", []))
            if "artifact_state_mismatch" not in reasons:
                reasons.append("artifact_state_mismatch")
            task.update(
                {
                    "status": "needs_review",
                    "updated_at": now,
                    "artifacts": run["artifacts"],
                    "summary": "Committed artifact requires taskstate reconciliation",
                    "status_reason": reasons,
                }
            )
            repaired_tasks.append(run_id)

    def update_operations(payload: dict[str, Any]) -> None:
        payload.setdefault("schema_version", SCHEMA_VERSION)
        payload.setdefault("dedupe_keys", [])
        payload.setdefault("notifications", [])
        payload.setdefault("replays", [])
        now = datetime.now(timezone.utc)
        for notification in payload["notifications"]:
            if notification.get("status") != "preparing":
                continue
            run_id = str(notification.get("run_id", ""))
            if run_id in committed:
                notification["status"] = "pending"
                notification["error"] = None
            elif _age_seconds(notification.get("recorded_at"), now) > stale_after_seconds:
                notification["status"] = "canceled"
                notification["error"] = "artifact_not_committed"
            else:
                continue
            notification["recorded_at"] = now.isoformat()
            repaired_notifications.append(run_id)

    locked_update_json(
        taskstate_path,
        lambda: {"schema_version": SCHEMA_VERSION, "tasks": []},
        update_tasks,
    )
    locked_update_json(
        operations_path,
        lambda: {
            "schema_version": SCHEMA_VERSION,
            "dedupe_keys": [],
            "notifications": [],
            "replays": [],
        },
        update_operations,
    )
    return {
        "taskstate": repaired_tasks,
        "notifications": repaired_notifications,
    }


def _committed_runs(runs_root: Path) -> dict[str, dict[str, Any]]:
    committed: dict[str, dict[str, Any]] = {}
    if not runs_root.exists():
        return committed
    for run_dir in runs_root.iterdir():
        manifest_path = run_dir / "manifest.json"
        report_path = run_dir / "report.json"
        if not run_dir.is_dir() or not manifest_path.exists() or not report_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if manifest.get("status") != "committed":
                continue
            run_id = str(manifest.get("run_id") or run_dir.name)
            artifacts = {
                str(entry["artifact"]): str(entry["path"])
                for entry in manifest.get("artifacts", [])
                if isinstance(entry, dict) and entry.get("artifact") and entry.get("path")
            }
            artifacts["manifest_json"] = str(manifest_path)
            committed[run_id] = {
                "preset": report.get("run_meta", {}).get("preset", "unknown"),
                "artifacts": artifacts,
            }
        except (OSError, ValueError, TypeError, KeyError):
            continue
    return committed


def _age_seconds(value: Any, now: datetime) -> float:
    if not isinstance(value, str):
        return float("inf")
    try:
        created = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return max((now - created).total_seconds(), 0.0)
    except ValueError:
        return float("inf")