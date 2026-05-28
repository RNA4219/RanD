from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path


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
        os.replace(temp_target, target)
    except Exception:
        _cleanup_owned_temp_file(temp_target, target_parent)
        raise


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
    """Cross-platform advisory file lock using lock file with O_EXCL.

    This provides a simple mutex mechanism for concurrent writes.
    Not suitable for distributed systems - use proper distributed locks there.
    """

    def __init__(self, lock_path: Path, timeout_seconds: float = 5.0, retry_interval: float = 0.1) -> None:
        self.lock_path = lock_path
        self._lock_parent = lock_path.parent.resolve()
        self.timeout_seconds = timeout_seconds
        self.retry_interval = retry_interval
        self._locked = False

    def acquire(self) -> bool:
        """Attempt to acquire the lock. Returns True if successful."""
        deadline = time.time() + self.timeout_seconds
        while time.time() < deadline:
            try:
                fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                self._locked = True
                return True
            except OSError:
                time.sleep(self.retry_interval)
        return False

    def release(self) -> None:
        """Release the lock if held."""
        if self._locked:
            _cleanup_owned_lock_file(self.lock_path, self._lock_parent)
            self._locked = False

    def __enter__(self) -> bool:
        return self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()


def with_file_lock(target_path: Path, timeout_seconds: float = 5.0) -> FileLock:
    """Return a FileLock for the given target file path."""
    lock_path = target_path.with_suffix(target_path.suffix + ".lock")
    return FileLock(lock_path, timeout_seconds=timeout_seconds)


def _cleanup_owned_lock_file(lock_path: Path, lock_parent: Path) -> None:
    try:
        resolved_lock = lock_path.resolve()
        resolved_parent = lock_parent.resolve()
    except OSError:
        return
    if resolved_lock.parent != resolved_parent or not resolved_lock.name.endswith(".lock"):
        return
    _cleanup_owned_temp_file(resolved_lock, resolved_parent)
