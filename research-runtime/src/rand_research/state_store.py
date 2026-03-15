from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from rand_research.models import ExecutionContext, SCHEMA_VERSION


DONE_STATUSES = {"done", "archived"}


def load_taskstate(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {"schema_version": SCHEMA_VERSION, "tasks": []}
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload.setdefault("tasks", [])
    return payload


def save_taskstate(state_path: Path, payload: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload.setdefault("schema_version", SCHEMA_VERSION)
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_memx_journal(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "entries": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload.setdefault("entries", [])
    return payload


def build_execution_context(
    state_path: Path,
    memory_path: Path,
    preset: str,
    limit: int = 5,
) -> ExecutionContext:
    task_payload = load_taskstate(state_path)
    memory_payload = load_memx_journal(memory_path)

    preset_tasks = [task for task in task_payload.get("tasks", []) if task.get("preset") == preset]
    preset_tasks.sort(key=lambda task: _sort_key(task.get("updated_at")), reverse=True)

    recent_tasks = [_task_digest(task) for task in preset_tasks[:limit]]
    open_tasks = [_task_digest(task) for task in preset_tasks if task.get("status") not in DONE_STATUSES][:limit]

    preset_entries = [entry for entry in memory_payload.get("entries", []) if entry.get("scope") == f"rand:{preset}"]
    preset_entries.sort(key=lambda entry: _sort_key(entry.get("recorded_at")), reverse=True)
    recent_memory_entries = [_memory_digest(entry) for entry in preset_entries[:limit]]

    known_urls: list[str] = []
    seen_urls: set[str] = set()
    for entry in preset_entries:
        for source in entry.get("sources", []):
            if not source or source in seen_urls:
                continue
            seen_urls.add(source)
            known_urls.append(source)

    return ExecutionContext(
        preset=preset,
        previous_run_count=len(preset_tasks),
        known_urls=known_urls,
        recent_tasks=recent_tasks,
        open_tasks=open_tasks,
        recent_memory_entries=recent_memory_entries,
    )


def upsert_task_record(
    state_path: Path,
    run_id: str,
    preset: str,
    status: str,
    artifacts: dict[str, str],
    summary: str,
    status_reason: list[str] | None = None,
) -> dict[str, Any]:
    payload = load_taskstate(state_path)
    records = payload.setdefault("tasks", [])
    now = datetime.utcnow().isoformat() + "Z"
    task_id = f"task-{run_id}"
    record = next((item for item in records if item["task_id"] == task_id), None)
    if record is None:
        record = {
            "task_id": task_id,
            "run_id": run_id,
            "preset": preset,
            "created_at": now,
        }
        records.append(record)
    record.update(
        {
            "status": status,
            "updated_at": now,
            "artifacts": artifacts,
            "summary": summary,
            "status_reason": status_reason or [],
        }
    )
    save_taskstate(state_path, payload)
    return record


def _task_digest(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task.get("task_id"),
        "run_id": task.get("run_id"),
        "status": task.get("status"),
        "updated_at": task.get("updated_at"),
        "summary": task.get("summary"),
    }


def _memory_digest(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "entry_id": entry.get("entry_id"),
        "recorded_at": entry.get("recorded_at"),
        "summary": entry.get("summary"),
        "sources": entry.get("sources", [])[:5],
    }


def _sort_key(value: str | None) -> str:
    return value or ""
