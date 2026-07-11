from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rand_research.recovery import reconcile_runtime_state


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_reconcile_repairs_committed_task_and_outbox_without_canceling_active_run(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    committed_dir = runs / "run-committed"
    report_path = committed_dir / "report.json"
    artifact_path = committed_dir / "report.json"
    manifest_path = committed_dir / "manifest.json"
    _write_json(
        report_path,
        {"run_meta": {"run_id": "run-committed", "preset": "preset"}, "status": "ok"},
    )
    _write_json(
        manifest_path,
        {
            "run_id": "run-committed",
            "status": "committed",
            "artifacts": [{"artifact": "report_json", "path": str(artifact_path)}],
        },
    )

    taskstate = tmp_path / "state" / "taskstate.json"
    operations = tmp_path / "state" / "operations.json"
    _write_json(
        taskstate,
        {
            "tasks": [
                {
                    "task_id": "task-run-committed",
                    "run_id": "run-committed",
                    "preset": "preset",
                    "status": "running",
                    "artifacts": {},
                }
            ]
        },
    )
    now = datetime.now(timezone.utc)
    _write_json(
        operations,
        {
            "notifications": [
                {"run_id": "run-committed", "status": "preparing", "recorded_at": now.isoformat()},
                {
                    "run_id": "run-crashed",
                    "status": "preparing",
                    "recorded_at": (now - timedelta(seconds=301)).isoformat(),
                },
                {"run_id": "run-active", "status": "preparing", "recorded_at": now.isoformat()},
            ]
        },
    )

    result = reconcile_runtime_state(runs, taskstate, operations)

    tasks = json.loads(taskstate.read_text(encoding="utf-8"))["tasks"]
    repaired = tasks[0]
    assert repaired["status"] == "needs_review"
    assert repaired["artifacts"]["manifest_json"] == str(manifest_path)
    assert "artifact_state_mismatch" in repaired["status_reason"]

    notifications = json.loads(operations.read_text(encoding="utf-8"))["notifications"]
    statuses = {item["run_id"]: item["status"] for item in notifications}
    assert statuses == {
        "run-committed": "pending",
        "run-crashed": "canceled",
        "run-active": "preparing",
    }
    assert result == {
        "taskstate": ["run-committed"],
        "notifications": ["run-committed", "run-crashed"],
    }


def test_reconcile_is_idempotent_for_matching_final_task(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    run_dir = runs / "run-1"
    report_path = run_dir / "report.json"
    manifest_path = run_dir / "manifest.json"
    artifacts = {"report_json": str(report_path), "manifest_json": str(manifest_path)}
    _write_json(report_path, {"run_meta": {"preset": "preset"}, "status": "ok"})
    _write_json(
        manifest_path,
        {
            "run_id": "run-1",
            "status": "committed",
            "artifacts": [{"artifact": "report_json", "path": str(report_path)}],
        },
    )
    taskstate = tmp_path / "state" / "taskstate.json"
    operations = tmp_path / "state" / "operations.json"
    _write_json(
        taskstate,
        {
            "tasks": [
                {
                    "task_id": "task-run-1",
                    "run_id": "run-1",
                    "preset": "preset",
                    "status": "done",
                    "artifacts": artifacts,
                }
            ]
        },
    )

    result = reconcile_runtime_state(runs, taskstate, operations)

    assert result == {"taskstate": [], "notifications": []}
    task = json.loads(taskstate.read_text(encoding="utf-8"))["tasks"][0]
    assert task["status"] == "done"