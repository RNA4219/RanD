from __future__ import annotations

import json
import multiprocessing
import os
import socket
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

from rand_research.io_utils import FileLock, _pid_is_alive
from rand_research.models import NormalizedItem
from rand_research.operations import record_notification_outbox
from rand_research.state_store import upsert_task_record
from rand_research.sync_writers import write_memx_journal, write_tracker_sync


def test_parallel_shared_json_updates_do_not_lose_records() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        task_path = root / "taskstate.json"
        operations_path = root / "operations.json"
        memx_path = root / "memx.json"
        tracker_path = root / "tracker.json"

        def update(index: int) -> None:
            run_id = f"run-{index:03d}"
            item = NormalizedItem(
                id=f"item-{index}",
                kind="paper",
                source_name="fixture",
                url=f"https://example.test/{index}",
                title=f"Item {index}",
            )
            upsert_task_record(task_path, run_id, "preset", "running", {}, f"run {index}")
            record_notification_outbox(
                operations_path,
                run_id,
                "preset",
                {"run_meta": {"run_id": run_id, "preset": "preset"}, "status": "ok"},
                {},
            )
            write_memx_journal(memx_path, run_id, "preset", [item], {})
            write_tracker_sync(tracker_path, run_id, "preset", [item], {"results": []})

        with ThreadPoolExecutor(max_workers=16) as pool:
            list(pool.map(update, range(100)))

        assert len(json.loads(task_path.read_text(encoding="utf-8"))["tasks"]) == 100
        operations = json.loads(operations_path.read_text(encoding="utf-8"))
        assert len(operations["notifications"]) == 100
        assert len(operations["dedupe_keys"]) == 100
        assert len(json.loads(memx_path.read_text(encoding="utf-8"))["entries"]) == 100
        assert len(json.loads(tracker_path.read_text(encoding="utf-8"))["events"]) == 100
        assert list(root.glob("*.lock")) == []


def _acquire_lock_and_exit(lock_path: str) -> None:
    lock = FileLock(Path(lock_path), timeout_seconds=1.0)
    if not lock.acquire():
        os._exit(2)
    os._exit(0)


def test_lock_timeout_does_not_reclaim_live_owner() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        lock_path = Path(temp_dir) / "state.json.lock"
        lock_path.write_text(
            json.dumps(
                {
                    "hostname": socket.gethostname(),
                    "pid": os.getpid(),
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "created_epoch": time.time(),
                    "nonce": "live-owner",
                }
            ),
            encoding="utf-8",
        )

        lock = FileLock(lock_path, timeout_seconds=0.05, retry_interval=0.005)
        assert lock.acquire() is False
        assert json.loads(lock_path.read_text(encoding="utf-8"))["nonce"] == "live-owner"


def test_lock_left_by_stopped_process_is_reclaimed() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        lock_path = Path(temp_dir) / "state.json.lock"
        process = multiprocessing.Process(target=_acquire_lock_and_exit, args=(str(lock_path),))
        process.start()
        process.join(timeout=5)
        assert process.exitcode == 0
        assert lock_path.exists()

        lock = FileLock(lock_path, timeout_seconds=1.0)
        assert lock.acquire() is True
        lock.release()
        assert not lock_path.exists()

def test_stale_lock_from_dead_local_process_is_reclaimed() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        lock_path = Path(temp_dir) / "state.json.lock"
        lock_path.write_text(
            json.dumps(
                {
                    "hostname": socket.gethostname(),
                    "pid": 2_147_483_647,
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "created_epoch": time.time(),
                    "nonce": "dead-owner",
                }
            ),
            encoding="utf-8",
        )

        lock = FileLock(lock_path, timeout_seconds=1.0)
        assert lock.acquire() is True
        metadata = json.loads(lock_path.read_text(encoding="utf-8"))
        assert metadata["pid"] == os.getpid()
        lock.release()
        assert not lock_path.exists()


def test_live_lock_is_not_reclaimed_for_age_alone() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        lock_path = Path(temp_dir) / "state.json.lock"
        lock_path.write_text(
            json.dumps(
                {
                    "hostname": socket.gethostname(),
                    "pid": os.getpid(),
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "created_epoch": time.time() - 100_000,
                    "nonce": "live-owner",
                }
            ),
            encoding="utf-8",
        )

        lock = FileLock(lock_path, timeout_seconds=0.2)
        assert lock.acquire() is False
        metadata = json.loads(lock_path.read_text(encoding="utf-8"))
        assert metadata["nonce"] == "live-owner"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX uses kill(pid, 0)")
def test_posix_pid_is_alive_treats_permission_error_as_alive() -> None:
    other_pid = os.getpid() + 1
    with patch("rand_research.io_utils.os.kill", side_effect=PermissionError("eperm")):
        assert _pid_is_alive(other_pid) is True
    with patch("rand_research.io_utils.os.kill", side_effect=ProcessLookupError("gone")):
        assert _pid_is_alive(other_pid) is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process handles")
@pytest.mark.parametrize(("winerror", "keep_lock"), [(5, True), (8, True), (87, False)])
def test_windows_open_process_error(winerror: int, keep_lock: bool) -> None:
    error = OSError(0, "OpenProcess failed", None, winerror)
    with patch("_winapi.OpenProcess", side_effect=error):
        assert _pid_is_alive(os.getpid() + 1) is keep_lock


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process handles")
def test_windows_wait_failure_keeps_lock_and_closes_handle() -> None:
    with (
        patch("_winapi.OpenProcess", return_value=123),
        patch("_winapi.WaitForSingleObject", side_effect=OSError("wait failed")),
        patch("_winapi.CloseHandle") as close_handle,
    ):
        assert _pid_is_alive(os.getpid() + 1)
        close_handle.assert_called_once_with(123)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows exit code 259")
def test_windows_detects_exit_even_with_still_active_exit_code() -> None:
    script = "import sys; sys.stdin.buffer.read(1); sys.exit(259)"
    with subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE) as process:
        assert _pid_is_alive(process.pid)
        process.communicate(input=b"x", timeout=10)
        assert process.returncode == 259
        assert not _pid_is_alive(process.pid)


def test_permission_error_is_not_treated_as_contention() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        lock = FileLock(Path(temp_dir) / "state.json.lock")
        with patch("rand_research.io_utils.os.open", side_effect=PermissionError("denied")):
            with pytest.raises(PermissionError):
                lock.acquire()
