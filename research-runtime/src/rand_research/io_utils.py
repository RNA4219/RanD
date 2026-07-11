from __future__ import annotations

import json
import os
import socket
import tempfile
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar
from uuid import uuid4

T = TypeVar("T")

_LOCAL_LOCKS_GUARD = threading.Lock()
_LOCAL_LOCKS: dict[str, threading.Lock] = {}


def _local_path_lock(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _LOCAL_LOCKS_GUARD:
        return _LOCAL_LOCKS.setdefault(key, threading.Lock())


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write text through a temp file created beside the target."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target_parent = target.parent.resolve()
    fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".tmp", prefix=f"{target.name}.")
    temp_target = Path(tmp_path)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
        _replace_with_retry(temp_target, target)
    except Exception:
        _cleanup_owned_temp_file(temp_target, target_parent)
        raise


def _replace_with_retry(source: Path, target: Path) -> None:
    deadline = time.monotonic() + 2.0
    while True:
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if os.name != "nt" or time.monotonic() >= deadline:
                raise
            time.sleep(0.005)

def _cleanup_owned_temp_file(temp_path: Path, target_parent: Path) -> None:
    try:
        resolved_temp = temp_path.resolve()
        resolved_parent = target_parent.resolve()
    except OSError:
        return
    if (resolved_temp.parent == resolved_parent):
        try:
            resolved_temp.unlink()
        except OSError:
            pass


class FileLock:
    """Cross-platform lock file with ownership metadata and stale recovery."""

    def __init__(
        self,
        lock_path: Path,
        timeout_seconds: float = 10.0,
        retry_interval: float = 0.01,
        stale_seconds: float = 300.0,
    ) -> None:
        self.lock_path = lock_path
        self._lock_parent = lock_path.parent.resolve()
        self.timeout_seconds = timeout_seconds
        self.retry_interval = retry_interval
        self.stale_seconds = stale_seconds
        self._locked = False
        self._nonce = uuid4().hex

    def acquire(self) -> bool:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            try:
                fd = self._open_exclusive()
                os.close(fd)
                try:
                    self.lock_path.write_text(
                        json.dumps(self._metadata(), ensure_ascii=False),
                        encoding="utf-8",
                    )
                except Exception:
                    self.lock_path.unlink(missing_ok=True)
                    raise
                self._locked = True
                return True
            except FileExistsError:
                if self._is_stale():
                    self._reclaim_stale()
                    continue
                time.sleep(self.retry_interval)
        return False

    def _open_exclusive(self) -> int:
        attempts = 3 if os.name == "nt" else 1
        last_error: PermissionError | None = None
        for attempt in range(attempts):
            try:
                return os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except PermissionError as exc:
                if self.lock_path.exists():
                    raise FileExistsError(str(self.lock_path)) from exc
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(0.001)
        assert last_error is not None
        raise last_error
    def release(self) -> None:
        if not self._locked:
            return
        try:
            resolved = self.lock_path.resolve()
            if resolved.parent != self._lock_parent or not resolved.name.endswith(".lock"):
                return
            metadata = json.loads(resolved.read_text(encoding="utf-8"))
            if metadata.get("nonce") != self._nonce:
                return
            deadline = time.monotonic() + 2.0
            while True:
                try:
                    resolved.unlink()
                    return
                except FileNotFoundError:
                    return
                except PermissionError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.005)
        finally:
            self._locked = False

    def _metadata(self) -> dict[str, Any]:
        return {
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_epoch": time.time(),
            "nonce": self._nonce,
        }

    def _is_stale(self) -> bool:
        try:
            stat = self.lock_path.stat()
            if time.time() - stat.st_mtime < 0.05:
                return False
            metadata = json.loads(self.lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            try:
                return time.time() - self.lock_path.stat().st_mtime > self.stale_seconds
            except OSError:
                return False
        age = time.time() - float(metadata.get("created_epoch", stat.st_mtime))
        if age > self.stale_seconds:
            return True
        if metadata.get("hostname") != socket.gethostname():
            return False
        pid = metadata.get("pid")
        return isinstance(pid, int) and not _pid_is_alive(pid)

    def _reclaim_stale(self) -> None:
        try:
            resolved = self.lock_path.resolve()
            if resolved.parent == self._lock_parent and resolved.name.endswith(".lock"):
                resolved.unlink(missing_ok=True)
        except OSError:
            return

    def __enter__(self) -> bool:
        return self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()


def with_file_lock(
    target_path: Path,
    timeout_seconds: float = 10.0,
    stale_seconds: float = 300.0,
) -> FileLock:
    lock_path = target_path.with_suffix(target_path.suffix + ".lock")
    return FileLock(
        lock_path,
        timeout_seconds=timeout_seconds,
        stale_seconds=stale_seconds,
    )


def _pid_is_alive(pid: int) -> bool:
    if pid == os.getpid():
        return True
    if os.name == "nt":
        import ctypes

        process_query_limited_information = 0x1000
        still_active = 259
        handle = ctypes.windll.kernel32.OpenProcess(
            process_query_limited_information,
            False,
            pid,
        )
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == still_active
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True

def locked_read_json(
    path: Path,
    default_factory: Callable[[], dict[str, Any]],
    *,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    local_lock = _local_path_lock(path)
    if not local_lock.acquire(timeout=timeout_seconds):
        raise TimeoutError(f"local lock acquisition timeout: {path}")
    try:
        remaining = max(deadline - time.monotonic(), 0.0)
        lock = with_file_lock(path, timeout_seconds=remaining)
        if not lock.acquire():
            raise TimeoutError(f"lock acquisition timeout: {path}")
        try:
            if not path.exists():
                return default_factory()
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError(f"shared JSON root must be an object: {path}")
            return payload
        finally:
            lock.release()
    finally:
        local_lock.release()

def locked_update_json(
    path: Path,
    default_factory: Callable[[], dict[str, Any]],
    updater: Callable[[dict[str, Any]], T],
    *,
    timeout_seconds: float = 10.0,
) -> T:
    deadline = time.monotonic() + timeout_seconds
    local_lock = _local_path_lock(path)
    if not local_lock.acquire(timeout=timeout_seconds):
        raise TimeoutError(f"local lock acquisition timeout: {path}")
    try:
        remaining = max(deadline - time.monotonic(), 0.0)
        lock = with_file_lock(path, timeout_seconds=remaining)
        if not lock.acquire():
            raise TimeoutError(f"lock acquisition timeout: {path}")
        try:
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError(f"shared JSON root must be an object: {path}")
            else:
                payload = default_factory()
            result = updater(payload)
            atomic_write_text(
                path,
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            )
            return result
        finally:
            lock.release()
    finally:
        local_lock.release()
