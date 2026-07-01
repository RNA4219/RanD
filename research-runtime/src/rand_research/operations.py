from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rand_research.io_utils import atomic_write_text
from rand_research.models import SCHEMA_VERSION


def load_operations_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "dedupe_keys": [], "notifications": [], "replays": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload.setdefault("dedupe_keys", [])
    payload.setdefault("notifications", [])
    payload.setdefault("replays", [])
    return payload


def save_operations_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload.setdefault("schema_version", SCHEMA_VERSION)
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def record_notification_outbox(
    path: Path,
    run_id: str,
    preset: str,
    report: dict[str, Any],
    artifact_paths: dict[str, str],
) -> dict[str, Any]:
    payload = load_operations_state(path)
    dedupe_key = f"note:{preset}:{run_id}"
    duplicate = dedupe_key in payload["dedupe_keys"]
    notification = {
        "schema_version": SCHEMA_VERSION,
        "notification_id": f"note-{run_id}",
        "run_id": run_id,
        "preset": preset,
        "dedupe_key": dedupe_key,
        "status": "duplicate_suppressed" if duplicate else "pending",
        "recorded_at": _now(),
        "reply_text": build_notification_text(report),
        "artifacts": artifact_paths,
        "attempts": 0,
        "error": None,
    }
    if not duplicate:
        payload["dedupe_keys"].append(dedupe_key)
        payload["notifications"].append(notification)
    save_operations_state(path, payload)
    return notification


def build_notification_text(report: dict[str, Any], max_length: int = 3000) -> str:
    meta = report.get("run_meta", {})
    summary = report.get("operational_summary", {})
    lines = [
        f"[RanD] {meta.get('preset', 'unknown')} {report.get('status', 'unknown')}",
        f"run_id: {meta.get('run_id', 'unknown')}",
        f"items: {summary.get('item_count', len(report.get('collected_items', [])))}",
    ]
    reasons = report.get("status_reason") or []
    if reasons:
        lines.append("reasons: " + ", ".join(reasons))
    for item in report.get("collected_items", [])[:3]:
        title = item.get("title")
        if title:
            lines.append(f"- {title[:80]}")
    text = "\n".join(lines)
    return text if len(text) <= max_length else text[: max_length - 3] + "..."


def plan_replay(taskstate_path: Path, operations_path: Path, task_id: str | None, trace_id: str | None = None) -> dict[str, Any]:
    state = json.loads(taskstate_path.read_text(encoding="utf-8")) if taskstate_path.exists() else {"tasks": []}
    task = _find_task(state.get("tasks", []), task_id, trace_id)
    if task is None:
        plan = {
            "schema_version": SCHEMA_VERSION,
            "status": "failed",
            "error": "task_not_found",
            "task_id": task_id,
            "trace_id": trace_id,
        }
    else:
        plan = {
            "schema_version": SCHEMA_VERSION,
            "status": "planned",
            "error": None,
            "task_id": task.get("task_id"),
            "run_id": task.get("run_id"),
            "preset": task.get("preset"),
            "resume_from": _resume_stage(task),
            "artifacts": task.get("artifacts", {}),
            "planned_at": _now(),
        }
    ops = load_operations_state(operations_path)
    ops["replays"].append(plan)
    save_operations_state(operations_path, ops)
    return plan


def pending_resend_payloads(operations_path: Path, limit: int = 10) -> dict[str, Any]:
    payload = load_operations_state(operations_path)
    pending = [item for item in payload.get("notifications", []) if item.get("status") in {"pending", "failed"}]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "pending_count": len(pending),
        "notifications": pending[:limit],
    }


def build_outbox_plan(operations_path: Path, limit: int = 20) -> dict[str, Any]:
    payload = load_operations_state(operations_path)
    notifications = [item for item in payload.get("notifications", []) if item.get("status") in {"pending", "failed"}]
    actions = [_notification_action(item) for item in notifications[:limit]]
    action_counts: dict[str, int] = {}
    for action in actions:
        action_counts[action["recommended_action"]] = action_counts.get(action["recommended_action"], 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "pending_count": len(notifications),
        "returned_count": len(actions),
        "action_counts": action_counts,
        "actions": actions,
    }


def mark_notification_attempt(
    operations_path: Path,
    notification_id: str,
    status: str,
    error: str | None = None,
) -> dict[str, Any]:
    payload = load_operations_state(operations_path)
    for notification in payload.get("notifications", []):
        if notification.get("notification_id") != notification_id:
            continue
        notification["status"] = status
        notification["attempts"] = int(notification.get("attempts", 0)) + 1
        notification["last_attempt_at"] = _now()
        notification["error"] = error
        save_operations_state(operations_path, payload)
        return notification
    raise KeyError(f"notification not found: {notification_id}")


def _notification_action(notification: dict[str, Any]) -> dict[str, Any]:
    status = notification.get("status", "unknown")
    attempts = int(notification.get("attempts", 0) or 0)
    notification_id = notification.get("notification_id")
    if status == "failed":
        recommended_action = "review_failure"
        reason = notification.get("error") or "notification previously failed"
    elif attempts > 0:
        recommended_action = "confirm_delivery"
        reason = "pending notification already has delivery attempts"
    else:
        recommended_action = "send_or_mark_sent"
        reason = "pending notification has not been attempted"
    return {
        "schema_version": SCHEMA_VERSION,
        "notification_id": notification_id,
        "run_id": notification.get("run_id"),
        "preset": notification.get("preset"),
        "status": status,
        "attempts": attempts,
        "recommended_action": recommended_action,
        "reason": reason,
        "next_commands": _next_commands(notification_id),
        "reply_preview": (notification.get("reply_text") or "")[:240],
        "artifacts": notification.get("artifacts", {}),
    }


def _next_commands(notification_id: str | None) -> list[str]:
    if not notification_id:
        return []
    return [
        f"python -m rand_research.cli mark-notification --notification-id {notification_id} --status sent",
        f"python -m rand_research.cli mark-notification --notification-id {notification_id} --status failed --error <reason>",
    ]


def _find_task(tasks: list[dict[str, Any]], task_id: str | None, trace_id: str | None) -> dict[str, Any] | None:
    for task in tasks:
        if task_id and task.get("task_id") == task_id:
            return task
        if trace_id and task.get("run_id") == trace_id:
            return task
    return None


def _resume_stage(task: dict[str, Any]) -> str:
    artifacts = task.get("artifacts", {})
    if not artifacts.get("report_json"):
        return "report"
    if task.get("status") in {"done", "needs_review"}:
        return "notify"
    return "research"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
