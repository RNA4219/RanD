from __future__ import annotations

import os
import tempfile
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
