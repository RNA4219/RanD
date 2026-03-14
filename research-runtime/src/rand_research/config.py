from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rand_research.paths import workspace_root


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_runtime_config() -> dict[str, Any]:
    return _load_json(workspace_root() / "configs" / "runtime.json")


def load_preset(name: str) -> dict[str, Any]:
    return _load_json(workspace_root() / "configs" / "presets" / f"{name}.json")


def load_schedule() -> dict[str, Any]:
    return _load_json(workspace_root() / "configs" / "schedule.json")
