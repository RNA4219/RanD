from __future__ import annotations

from pathlib import Path


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def installer_root() -> Path:
    return workspace_root().parent / "r-and-d-agent-installer" / ".installed" / "repos"
