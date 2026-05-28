import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rand_research.io_utils import atomic_write_text


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
