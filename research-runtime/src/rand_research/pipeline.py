from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from rand_research.config import load_preset, load_runtime_config
from rand_research.fetchers import collect_source
from rand_research.integrations import run_gate, run_insight, write_memx_journal, write_tracker_sync
from rand_research.models import ExecutionContext, NormalizedItem, RunMeta
from rand_research.paths import workspace_root
from rand_research.reports import save_run_outputs
from rand_research.state_store import build_execution_context, upsert_task_record


def run_once(preset_name: str, max_items_override: int | None = None) -> dict[str, Any]:
    runtime = load_runtime_config()
    preset = load_preset(preset_name)
    max_items = max_items_override or preset.get("max_items") or runtime["default_max_items"]
    run_id = datetime.utcnow().strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:8]
    run_dir = workspace_root() / runtime["save_root"] / run_id
    state_path = workspace_root() / runtime["state_path"]
    memory_path = workspace_root() / runtime["memory_log_path"]

    pre_state_context = build_execution_context(state_path, memory_path, preset_name)
    meta = RunMeta(
        run_id=run_id,
        preset=preset_name,
        started_at=datetime.utcnow().isoformat() + "Z",
        prompt_template=preset.get("prompt_template"),
        max_items=max_items,
        save_dir=str(run_dir),
        target_sites=preset.get("seed_urls", []),
        state_context_summary=pre_state_context.summary(),
    )

    task_record = upsert_task_record(
        state_path,
        run_id,
        preset_name,
        "queued",
        {},
        f"Preparing {preset_name} with {pre_state_context.previous_run_count} prior runs in context",
    )

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

    items = _apply_execution_context(_dedupe_items(items), pre_state_context)[:max_items]
    meta.errors = errors
    upsert_task_record(
        state_path,
        run_id,
        preset_name,
        "running",
        {},
        f"Collected {len(items)} items for {preset_name} after checking prior state",
    )

    insight_payload = run_insight(items) if runtime["enable_insight"] else {"mode": "disabled", "results": []}
    gate_payload = run_gate(items) if runtime["enable_gate"] and preset.get("gate_enabled") else {"mode": "disabled", "results": []}
    meta.finish()

    memx_record = write_memx_journal(workspace_root() / runtime["memory_log_path"], run_id, preset_name, items, {})
    tracker_event = write_tracker_sync(workspace_root() / runtime["tracker_sync_path"], run_id, preset_name, items, gate_payload)

    interim_post_state_context = build_execution_context(state_path, memory_path, preset_name)
    artifacts = save_run_outputs(
        run_dir,
        meta,
        items,
        insight_payload,
        gate_payload,
        task_record,
        memx_record,
        tracker_event,
        pre_state_context.to_dict(),
        interim_post_state_context.to_dict(),
    )
    task_record = upsert_task_record(
        state_path,
        run_id,
        preset_name,
        "done" if not errors else "needs_review",
        artifacts,
        f"{len(items)} items collected for {preset_name}",
    )
    post_state_context = build_execution_context(state_path, memory_path, preset_name)
    artifacts = save_run_outputs(
        run_dir,
        meta,
        items,
        insight_payload,
        gate_payload,
        task_record,
        memx_record,
        tracker_event,
        pre_state_context.to_dict(),
        post_state_context.to_dict(),
    )

    return {
        "meta": meta.to_dict(),
        "report": {
            "run_meta": meta.to_dict(),
            "collected_items": [item.to_dict() for item in items],
            "state_context": {
                "before": pre_state_context.to_dict(),
                "after": post_state_context.to_dict(),
            },
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


def _apply_execution_context(items: list[NormalizedItem], execution_context: ExecutionContext) -> list[NormalizedItem]:
    known_urls = set(execution_context.known_urls)
    enriched: list[NormalizedItem] = []
    for item in items:
        seen_before = item.url in known_urls
        item.metadata["seen_before"] = seen_before
        item.metadata["previous_run_count"] = execution_context.previous_run_count
        if seen_before:
            if "previously_seen" not in item.tags:
                item.tags.append("previously_seen")
            item.evidence.append("Previously recorded in memx journal for this preset")
            item.high_priority = False
            item.priority = max(item.priority - 5, 0)
        enriched.append(item)
    return sorted(enriched, key=lambda item: (item.metadata.get("seen_before", False), -item.priority, item.title))
