from __future__ import annotations

from argparse import Namespace
from unittest.mock import patch

import pytest

from rand_research.commands import run as run_commands


@pytest.mark.parametrize(("status", "expected"), [("ok", 0), ("failed", 1), ("degraded", 2), ("unknown", 1)])
def test_run_once_exit_code_follows_report_status(status: str, expected: int) -> None:
    args = Namespace(command="run-once", preset="preset", max_items=0)
    with patch.object(run_commands, "run_once", return_value={"report": {"status": status}}):
        assert run_commands.handle_run_command(args) == expected


@pytest.mark.parametrize(("statuses", "expected"), [(["ok", "ok"], 0), (["ok", "degraded"], 2), (["degraded", "failed"], 1)])
def test_schedule_exit_code_uses_worst_child_status(statuses: list[str], expected: int) -> None:
    args = Namespace(command="run-schedule")
    schedule = {"jobs": [{"name": f"job-{i}", "preset": f"preset-{i}"} for i in range(len(statuses))]}
    results = iter({"report": {"status": status}} for status in statuses)
    with patch.object(run_commands, "load_schedule", return_value=schedule):
        with patch.object(run_commands, "run_once", side_effect=lambda *_: next(results)):
            assert run_commands.handle_run_command(args) == expected


@pytest.mark.parametrize(("status", "expected"), [("ok", 0), ("failed", 1), ("degraded", 2)])
def test_heartbeat_exit_code_follows_report_status(status: str, expected: int) -> None:
    args = Namespace(command="heartbeat", preset="preset", max_items=5, dry_run=False, summary_only=False)
    with patch.object(run_commands, "run_once", return_value={"report": {"status": status}}):
        assert run_commands.handle_run_command(args) == expected