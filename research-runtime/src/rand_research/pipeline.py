from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from rand_research.config import load_preset, load_runtime_config
from rand_research.fetchers import collect_source
from rand_research.integrations import run_gate, run_insight, write_memx_journal, write_tracker_sync
from rand_research.models import NormalizedItem, RunMeta
from rand_research.paths import workspace_root
from rand_research.reports import save_run_outputs
from rand_research.state_store import upsert_task_record


def run_once(preset_name: str, max_items_override: int | None = None) -> dict[str, Any]:
    runtime = load_runtime_config()
    preset = load_preset(preset_name)
    max_items = max_items_override or preset.get("max_items") or runtime["default_max_items"]
    run_id = datetime.utcnow().strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:8]
    run_dir = workspace_root() / runtime["save_root"] / run_id
    meta = RunMeta(
        run_id=run_id,
        preset=preset_name,
        started_at=datetime.utcnow().isoformat() + "Z",
        prompt_template=preset.get("prompt_template"),
        max_items=max_items,
        save_dir=str(run_dir),
        target_sites=preset.get("seed_urls", []),
    )
    state_path = workspace_root() / runtime["state_path"]
    task_record = upsert_task_record(state_path, run_id, preset_name, "queued", {}, f"Starting {preset_name}")
    items: list[NormalizedItem] = []
    errors: list[str] = []
    if "composed_presets" in preset:
        for child in preset["composed_presets"]:
            child_result = run_once(child, max_items_override=max_items)
            items.extend(NormalizedItem(**item) for item in child_result["report"]["collected_items"])
            errors.extend(child_result["meta"].get("errors", []))
    else:
        for source in sorted(preset.get("sources", []), key=lambda entry: entry.get("priority", 99)):
            try:
                items.extend(
                    collect_source(
                        source,
                        runtime["default_user_agent"],
                        runtime["default_timeout_seconds"],
                        max_items=max_items,
                    )
                )
            except Exception as exc:
                errors.append(f"{source['name']}: {exc}")
    items = _dedupe_items(items)[:max_items]
    meta.errors = errors
    upsert_task_record(state_path, run_id, preset_name, "running", {}, f"Collected {len(items)} items")
    insight_payload = run_insight(items) if runtime["enable_insight"] else {"mode": "disabled", "results": []}
    gate_payload = run_gate(items) if runtime["enable_gate"] and preset.get("gate_enabled") else {"mode": "disabled", "results": []}
    meta.finish()
    memx_record = write_memx_journal(workspace_root() / runtime["memory_log_path"], run_id, preset_name, items, {})
    tracker_event = write_tracker_sync(workspace_root() / runtime["tracker_sync_path"], run_id, preset_name, items, gate_payload)
    artifacts = save_run_outputs(run_dir, meta, items, insight_payload, gate_payload, task_record, memx_record, tracker_event)
    task_record = upsert_task_record(
        state_path,
        run_id,
        preset_name,
        "done" if not errors else "needs_review",
        artifacts,
        f"{len(items)} items collected for {preset_name}",
    )
    return {
        "meta": meta.to_dict(),
        "report": {
            "run_meta": meta.to_dict(),
            "collected_items": [item.to_dict() for item in items],
            "artifacts": artifacts,
            "taskstate_refs": [task_record],
            "memx_refs": [memx_record],
            "tracker_sync_refs": [tracker_event],
        },
        "insight": insight_payload,
        "gate": gate_payload,
    }


def _dedupe_items(items: list[NormalizedItem]) -> list[NormalizedItem]:
    deduped: list[NormalizedItem] = []
    seen: set[str] = set()
    for item in items:
        key = item.url or item.title
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
