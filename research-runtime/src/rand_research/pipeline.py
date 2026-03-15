from __future__ import annotations

from datetime import datetime
from pathlib import Path
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
    tracker_path = workspace_root() / runtime["tracker_sync_path"]

    dependency_health: dict[str, str] = {
        "sources": "ok",
        "state": "ok",
        "insight": "ok",
        "gate": "ok",
        "memx": "ok",
        "tracker": "ok",
    }
    status_reasons: list[str] = []
    errors: list[str] = []

    try:
        pre_state_context = build_execution_context(state_path, memory_path, preset_name)
    except Exception as exc:
        pre_state_context = ExecutionContext(preset=preset_name)
        dependency_health["state"] = "failed"
        status_reasons.append("state_read_failed")
        errors.append(f"state_read_failed: {exc}")

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

    task_record = _safe_task_update(
        state_path,
        run_id,
        preset_name,
        "queued",
        {},
        f"Preparing {preset_name} with {pre_state_context.previous_run_count} prior runs in context",
        [],
        dependency_health,
        status_reasons,
        errors,
    )

    items: list[NormalizedItem] = []
    if "composed_presets" in preset:
        child_reports: list[dict[str, Any]] = []
        for child in preset["composed_presets"]:
            child_result = run_once(child, max_items_override=max_items)
            child_report = child_result["report"]
            child_reports.append(child_report)
            items.extend(NormalizedItem(**item) for item in child_report.get("collected_items", []))
            if child_report.get("status") == "degraded":
                status_reasons.append(f"{child}_degraded")
            elif child_report.get("status") == "failed":
                status_reasons.append(f"{child}_failed")
        items = _apply_execution_context(_dedupe_items(items), pre_state_context)[:max_items]
        if child_reports and all(report.get("status") == "failed" for report in child_reports):
            dependency_health["sources"] = "failed"
        elif any(report.get("status") != "ok" for report in child_reports):
            dependency_health["sources"] = "degraded"
    else:
        source_failures = 0
        sources = sorted(preset.get("sources", []), key=lambda entry: entry.get("priority", 99))
        for source in sources:
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
                source_failures += 1
                errors.append(f"{source['name']}: {exc}")
        items = _apply_execution_context(_dedupe_items(items), pre_state_context)[:max_items]
        if source_failures and not items:
            dependency_health["sources"] = "failed"
            status_reasons.append("source_all_failed")
        elif source_failures:
            dependency_health["sources"] = "degraded"
            status_reasons.append("source_partial_failure")

    meta.errors = errors
    task_record = _safe_task_update(
        state_path,
        run_id,
        preset_name,
        "running",
        {},
        f"Collected {len(items)} items for {preset_name} after checking prior state",
        status_reasons,
        dependency_health,
        status_reasons,
        errors,
    )

    insight_payload = run_insight(items) if runtime["enable_insight"] else _disabled_payload("insight")
    dependency_health["insight"] = insight_payload["status"]
    if insight_payload["status"] != "ok":
        status_reasons.append("insight_failed")

    gate_dependency_health = {
        "sources": dependency_health["sources"],
        "state": dependency_health["state"],
        "insight": dependency_health["insight"],
    }
    gate_payload = run_gate(items, gate_dependency_health) if runtime["enable_gate"] and preset.get("gate_enabled") else _disabled_payload("gate", dependency_health=gate_dependency_health)
    dependency_health["gate"] = gate_payload["status"]
    if gate_payload["status"] != "ok":
        status_reasons.append("gate_failed")

    meta.finish()
    artifact_paths = _expected_artifacts(run_dir)

    try:
        memx_record = write_memx_journal(memory_path, run_id, preset_name, items, artifact_paths) if runtime["enable_memx"] else _disabled_log("memx", run_id, preset_name)
        dependency_health["memx"] = memx_record.get("status", "ok")
    except Exception as exc:
        memx_record = _failed_log("memx", run_id, preset_name, str(exc), artifact_paths)
        dependency_health["memx"] = "degraded"
        status_reasons.append("memx_failed")

    try:
        tracker_event = write_tracker_sync(tracker_path, run_id, preset_name, items, gate_payload) if runtime["enable_tracker_bridge"] else _disabled_log("tracker", run_id, preset_name)
        dependency_health["tracker"] = tracker_event.get("status", "ok")
    except Exception as exc:
        tracker_event = _failed_log("tracker", run_id, preset_name, str(exc), artifact_paths)
        dependency_health["tracker"] = "degraded"
        status_reasons.append("tracker_failed")

    final_status = _final_status(dependency_health, status_reasons)
    task_state = {"ok": "done", "degraded": "needs_review", "failed": "failed"}[final_status]
    task_record = _safe_task_update(
        state_path,
        run_id,
        preset_name,
        task_state,
        artifact_paths,
        f"{len(items)} items collected for {preset_name}",
        status_reasons,
        dependency_health,
        status_reasons,
        errors,
    )

    try:
        post_state_context = build_execution_context(state_path, memory_path, preset_name)
    except Exception as exc:
        post_state_context = ExecutionContext(preset=preset_name)
        dependency_health["state"] = "failed"
        status_reasons.append("state_write_failed")
        errors.append(f"state_write_failed: {exc}")
        final_status = _final_status(dependency_health, status_reasons)
        task_state = {"ok": "done", "degraded": "needs_review", "failed": "failed"}[final_status]
        task_record = {
            **task_record,
            "status": task_state,
            "status_reason": _unique(status_reasons),
        }

    try:
        artifacts, report_payload = save_run_outputs(
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
            final_status,
            _unique(status_reasons),
            dependency_health,
        )
    except Exception as exc:
        dependency_health["state"] = "failed"
        status_reasons.append("report_save_failed")
        final_status = "failed"
        task_record = _safe_task_update(
            state_path,
            run_id,
            preset_name,
            "failed",
            artifact_paths,
            f"Report save failed for {preset_name}",
            _unique(status_reasons),
            dependency_health,
            status_reasons,
            errors,
        )
        report_payload = {
            "schema_version": meta.schema_version,
            "status": final_status,
            "status_reason": _unique(status_reasons),
            "run_meta": meta.to_dict(),
            "collected_items": [item.to_dict() for item in items],
            "state_context": {
                "before": pre_state_context.to_dict(),
                "after": post_state_context.to_dict(),
            },
            "dependency_health": dependency_health,
            "artifacts": artifact_paths,
            "taskstate_refs": [task_record],
            "memx_refs": [memx_record],
            "tracker_sync_refs": [tracker_event],
            "error": str(exc),
        }
        artifacts = artifact_paths

    return {
        "meta": meta.to_dict() | {"status": final_status, "status_reason": _unique(status_reasons)},
        "report": report_payload,
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


def _safe_task_update(
    state_path: Path,
    run_id: str,
    preset_name: str,
    status: str,
    artifacts: dict[str, str],
    summary: str,
    status_reason: list[str],
    dependency_health: dict[str, str],
    mutable_reasons: list[str],
    errors: list[str],
) -> dict[str, Any]:
    try:
        return upsert_task_record(state_path, run_id, preset_name, status, artifacts, summary, _unique(status_reason))
    except Exception as exc:
        dependency_health["state"] = "failed"
        mutable_reasons.append("state_write_failed")
        errors.append(f"state_write_failed: {exc}")
        return {
            "task_id": f"task-{run_id}",
            "run_id": run_id,
            "preset": preset_name,
            "status": status,
            "artifacts": artifacts,
            "summary": summary,
            "status_reason": _unique(status_reason),
        }


def _disabled_payload(name: str, dependency_health: dict[str, str] | None = None) -> dict[str, Any]:
    payload = {
        "schema_version": RunMeta.__dataclass_fields__["schema_version"].default,
        "status": "ok",
        "mode": "disabled",
        "results": [],
        "error": None,
    }
    if dependency_health is not None:
        payload["dependency_health"] = dependency_health
    return payload


def _disabled_log(kind: str, run_id: str, preset_name: str) -> dict[str, Any]:
    key_name = "entry_id" if kind == "memx" else "sync_id"
    return {
        "schema_version": RunMeta.__dataclass_fields__["schema_version"].default,
        key_name: f"{kind}-{run_id}",
        "preset": preset_name,
        "status": "ok",
        "error": None,
        "sources": [],
        "items": [],
        "gate_recommendations": [],
        "artifacts": {},
    }


def _failed_log(kind: str, run_id: str, preset_name: str, error: str, artifacts: dict[str, str]) -> dict[str, Any]:
    key_name = "entry_id" if kind == "memx" else "sync_id"
    payload = {
        "schema_version": RunMeta.__dataclass_fields__["schema_version"].default,
        key_name: f"{kind}-{run_id}",
        "preset": preset_name,
        "status": "degraded",
        "error": error,
    }
    if kind == "memx":
        payload.update({"scope": f"rand:{preset_name}", "sources": [], "artifacts": artifacts})
    else:
        payload.update({"items": [], "gate_recommendations": []})
    return payload


def _expected_artifacts(run_dir: Path) -> dict[str, str]:
    return {
        "report_md": str(run_dir / "report.md"),
        "report_json": str(run_dir / "report.json"),
        "insight_json": str(run_dir / "insight.json"),
        "gate_json": str(run_dir / "gate.json"),
        "meta_json": str(run_dir / "meta.json"),
        "tracker_sync_json": str(run_dir / "tracker_sync.json"),
        "memx_journal_json": str(run_dir / "memx_journal.json"),
        "state_context_json": str(run_dir / "state_context.json"),
    }


def _final_status(dependency_health: dict[str, str], status_reasons: list[str]) -> str:
    reasons = set(status_reasons)
    if dependency_health.get("state") == "failed" or dependency_health.get("sources") == "failed" or "report_save_failed" in reasons:
        return "failed"
    if any(value != "ok" for value in dependency_health.values()) or reasons:
        return "degraded"
    return "ok"


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
