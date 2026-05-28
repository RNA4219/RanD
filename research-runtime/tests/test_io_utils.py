import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from rand_research.io_utils import atomic_write_text, FileLock, with_file_lock


class IoUtilsTests(unittest.TestCase):
    def test_atomic_write_replaces_target_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "report.json"
            path.write_text("old", encoding="utf-8")

            atomic_write_text(path, "new")

            self.assertEqual(path.read_text(encoding="utf-8"), "new")
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_atomic_write_keeps_existing_target_when_replace_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            path.write_text("stable", encoding="utf-8")

            with patch("rand_research.io_utils.os.replace", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    atomic_write_text(path, "partial")

            self.assertEqual(path.read_text(encoding="utf-8"), "stable")
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_atomic_write_does_not_cleanup_temp_outside_target_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as outside_dir:
            path = Path(temp_dir) / "state.json"
            path.write_text("stable", encoding="utf-8")
            fd, outside_temp = tempfile.mkstemp(dir=outside_dir, suffix=".tmp")
            os.close(fd)

            with patch("rand_research.io_utils.tempfile.mkstemp", return_value=(os.open(outside_temp, os.O_WRONLY), outside_temp)):
                with patch("rand_research.io_utils.os.replace", side_effect=RuntimeError("boom")):
                    with self.assertRaises(RuntimeError):
                        atomic_write_text(path, "partial")

            self.assertTrue(Path(outside_temp).exists())
            self.assertEqual(path.read_text(encoding="utf-8"), "stable")


if __name__ == "__main__":
    unittest.main()


class FileLockTests(unittest.TestCase):
    def test_file_lock_acquires_and_releases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "state.json.lock"
            lock = FileLock(lock_path)
            self.assertTrue(lock.acquire())
            self.assertTrue(lock_path.exists())
            lock.release()
            self.assertFalse(lock_path.exists())

    def test_file_lock_context_manager(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "test.lock"
            with FileLock(lock_path) as acquired:
                self.assertTrue(acquired)
                self.assertTrue(lock_path.exists())
            self.assertFalse(lock_path.exists())

    def test_file_lock_blocks_concurrent_access(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "concurrent.lock"
            results: list[str] = []

            def holder() -> None:
                with FileLock(lock_path, timeout_seconds=2.0) as acquired:
                    if acquired:
                        results.append("holder_acquired")
                        time.sleep(0.5)
                        results.append("holder_released")

            def waiter() -> None:
                time.sleep(0.1)
                with FileLock(lock_path, timeout_seconds=0.2) as acquired:
                    if acquired:
                        results.append("waiter_acquired")
                    else:
                        results.append("waiter_blocked")

            holder_thread = threading.Thread(target=holder)
            waiter_thread = threading.Thread(target=waiter)

            holder_thread.start()
            waiter_thread.start()

            holder_thread.join()
            waiter_thread.join()

            self.assertIn("holder_acquired", results)
            self.assertIn("holder_released", results)
            self.assertIn("waiter_blocked", results)

    def test_file_lock_timeout_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "timeout.lock"
            lock1 = FileLock(lock_path, timeout_seconds=0.1)
            lock2 = FileLock(lock_path, timeout_seconds=0.1)

            self.assertTrue(lock1.acquire())
            self.assertFalse(lock2.acquire())
            lock1.release()

    def test_with_file_lock_helper(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir) / "data.json"
            lock = with_file_lock(target_path)
            with lock as acquired:
                self.assertTrue(acquired)
                self.assertTrue(lock.lock_path.exists())
            self.assertFalse(lock.lock_path.exists())
