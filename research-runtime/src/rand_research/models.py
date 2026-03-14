from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class NormalizedItem:
    id: str
    kind: str
    source_name: str
    url: str
    title: str
    published_at: str | None = None
    authors: list[str] = field(default_factory=list)
    summary: str = ""
    claims: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    priority: int = 0
    high_priority: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunMeta:
    run_id: str
    preset: str
    started_at: str
    finished_at: str | None = None
    prompt_template: str | None = None
    max_items: int = 0
    save_dir: str = ""
    errors: list[str] = field(default_factory=list)
    target_sites: list[str] = field(default_factory=list)

    def finish(self) -> None:
        self.finished_at = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
