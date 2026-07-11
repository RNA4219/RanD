from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from rand_research.pipeline import run_once


def _runtime() -> dict:
    return {
        "default_max_items": 1,
        "default_timeout_seconds": 1,
        "default_user_agent": "test",
        "enable_gate": False,
        "enable_insight": False,
        "enable_memx": False,
        "enable_tracker_bridge": False,
        "downstream_handoff_mode": "dry_run",
        "save_root": "runs",
        "state_path": "state/taskstate.json",
        "memory_log_path": "state/memx.json",
        "tracker_sync_path": "state/tracker.json",
        "operations_state_path": "state/operations.json",
        "tracker_bridge_db_path": "state/tracker-bridge.db",
        "tracker_connection_id": "github-main",
    }


def _preset() -> dict:
    return {
        "name": "offline",
        "sources": [],
        "max_items": 1,
        "insight_enabled": False,
        "gate_enabled": False,
    }


def test_run_once_returns_report_and_commits_before_done(tmp_path: Path) -> None:
    with patch("rand_research.pipeline.load_runtime_config", return_value=_runtime()):
        with patch("rand_research.pipeline.load_preset", return_value=_preset()):
            with patch("rand_research.pipeline.workspace_root", return_value=tmp_path):
                result = run_once("offline")

    assert set(result) == {"meta", "report", "insight", "gate", "operations"}
    assert result["report"]["status"] == "ok"
    run_id = result["meta"]["run_id"]
    run_dir = tmp_path / "runs" / run_id
    assert (run_dir / "manifest.json").exists()

    state = json.loads((tmp_path / "state" / "taskstate.json").read_text(encoding="utf-8"))
    task = next(item for item in state["tasks"] if item["run_id"] == run_id)
    assert task["status"] == "done"
    assert task["artifacts"]["manifest_json"] == str(run_dir / "manifest.json")

    operations = json.loads((tmp_path / "state" / "operations.json").read_text(encoding="utf-8"))
    notification = next(item for item in operations["notifications"] if item["run_id"] == run_id)
    assert notification["status"] == "pending"


def test_report_failure_never_leaves_done_or_deliverable_outbox(tmp_path: Path) -> None:
    with patch("rand_research.pipeline.load_runtime_config", return_value=_runtime()):
        with patch("rand_research.pipeline.load_preset", return_value=_preset()):
            with patch("rand_research.pipeline.workspace_root", return_value=tmp_path):
                with patch("rand_research.pipeline.save_run_outputs", side_effect=OSError("injected")):
                    result = run_once("offline")

    assert result["report"]["status"] == "failed"
    run_id = result["meta"]["run_id"]
    assert not (tmp_path / "runs" / run_id).exists()

    state = json.loads((tmp_path / "state" / "taskstate.json").read_text(encoding="utf-8"))
    task = next(item for item in state["tasks"] if item["run_id"] == run_id)
    assert task["status"] == "failed"
    assert task["artifacts"] == {}

    operations = json.loads((tmp_path / "state" / "operations.json").read_text(encoding="utf-8"))
    notification = next(item for item in operations["notifications"] if item["run_id"] == run_id)
    assert notification["status"] == "canceled"