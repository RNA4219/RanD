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
class ExecutionContext:
    preset: str
    previous_run_count: int = 0
    known_urls: list[str] = field(default_factory=list)
    recent_tasks: list[dict[str, Any]] = field(default_factory=list)
    open_tasks: list[dict[str, Any]] = field(default_factory=list)
    recent_memory_entries: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary(self) -> dict[str, Any]:
        return {
            "preset": self.preset,
            "previous_run_count": self.previous_run_count,
            "known_url_count": len(self.known_urls),
            "recent_task_count": len(self.recent_tasks),
            "open_task_count": len(self.open_tasks),
            "recent_memory_entry_count": len(self.recent_memory_entries),
        }


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
    state_context_summary: dict[str, Any] = field(default_factory=dict)

    def finish(self) -> None:
        self.finished_at = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
