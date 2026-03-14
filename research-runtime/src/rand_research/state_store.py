from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def load_taskstate(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {"tasks": []}
    return json.loads(state_path.read_text(encoding="utf-8"))


def save_taskstate(state_path: Path, payload: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def upsert_task_record(
    state_path: Path,
    run_id: str,
    preset: str,
    status: str,
    artifacts: dict[str, str],
    summary: str,
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
        }
    )
    save_taskstate(state_path, payload)
    return record
