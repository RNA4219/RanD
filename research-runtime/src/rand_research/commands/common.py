from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def resolve_path(value: str, base: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def print_json(payload: dict[str, Any] | list[Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
