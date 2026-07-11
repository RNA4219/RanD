from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from rand_research.config import load_preset, load_runtime_config
from rand_research.downstream import build_downstream_handoff
from rand_research.fetchers import collect_source
from rand_research.integrations import run_gate, run_insight
from rand_research.kano import build_audit_artifacts, build_kano_artifacts
from rand_research.models import ExecutionContext, NormalizedItem, RunMeta
from rand_research.operations import reserve_notification_outbox, transition_notification_outbox
from rand_research.paths import workspace_root
from rand_research.recovery import reconcile_runtime_state
from rand_research.reports import save_run_outputs
from rand_research.state_store import build_execution_context, upsert_task_record
from rand_research.sync_writers import write_memx_journal, write_tracker_sync
from rand_research.tracker_transport import TrackerBridgeTransport


def run_once(
    preset_name: str,
    max_items_override: int | None = None,
    delivery_mode_override: str | None = None,
    confirm_live: bool = False,
) -> dict[str, Any]:
    runtime = load_runtime_config()
    preset = load_preset(preset_name)
    max_items = max_items_override or preset.get("max_items") or runtime["default_max_items"]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:8]
    run_dir = workspace_root() / runtime["save_root"] / run_id
    state_path = workspace_root() / runtime["state_path"]
    memory_path = workspace_root() / runtime["memory_log_path"]
    tracker_path = workspace_root() / runtime["tracker_sync_path"]
    operations_path = workspace_root() / runtime.get("operations_state_path", "state/operations-state.json")

    dependency_health: dict[str, str] = {
        "sources": "ok",
        "state": "ok",
        "report": "ok",
        "insight": "ok",
        "gate": "ok",
        "memx": "ok",
        "tracker": "ok",
        "delivery": "ok",
    }
    status_reasons: list[str] = []
    errors: list[str] = []

    try:
        reconcile_runtime_state(run_dir.parent, state_path, operations_path)
    except Exception as exc:
        dependency_health["state"] = "degraded"
        status_reasons.append("state_reconciliation_failed")
        errors.append(f"state_reconciliation_failed: {exc}")

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
        started_at=datetime.now(timezone.utc).isoformat(),
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

    insight_enabled = runtime["enable_insight"] and preset.get("insight_enabled", True)
    insight_payload = run_insight(items) if insight_enabled else _disabled_payload("insight")
    dependency_health["insight"] = insight_payload["status"]
    if insight_payload["status"] != "ok":
        status_reasons.append("insight_failed")

    gate_dependency_health = {
        "sources": dependency_health["sources"],
        "state": dependency_health["state"],
        "report": dependency_health["report"],
        "insight": dependency_health["insight"],
    }
    gate_payload = run_gate(items, gate_dependency_health) if runtime["enable_gate"] and preset.get("gate_enabled") else _disabled_payload("gate", dependency_health=gate_dependency_health)
    dependency_health["gate"] = gate_payload["status"]
    if gate_payload["status"] != "ok":
        status_reasons.append("gate_failed")

    extra_payloads: dict[str, dict[str, Any]] = {}
    if preset.get("mode") == "kano_requirements":
        extra_payloads = build_kano_artifacts(items, preset, run_id)
    elif preset.get("mode") == "kano_audit":
        extra_payloads = build_audit_artifacts(items, preset, run_id)
    (
        downstream_handoff_mode,
        downstream_transport,
        live_configuration_error,
        live_confirmed,
    ) = _prepare_delivery(
        runtime,
        preset,
        delivery_mode_override,
        confirm_live,
        run_id,
    )
    downstream_handoff = (
        build_downstream_handoff(
            extra_payloads,
            run_id,
            mode=downstream_handoff_mode,
            transport=downstream_transport,
        )
        if extra_payloads
        else None
    )
    if downstream_handoff_mode == "live" and downstream_handoff:
        delivery = downstream_handoff.get("delivery", {})
        if live_configuration_error:
            delivery["error"] = live_configuration_error
            delivery["success"] = False
            delivery["destination_verdict"] = "failed"
        verdict = delivery.get("destination_verdict")
        if verdict == "degraded":
            dependency_health["delivery"] = "degraded"
            status_reasons.append("delivery_partial_failure")
        elif delivery.get("success") is not True or verdict == "failed":
            dependency_health["delivery"] = "failed"
            status_reasons.append(
                "live_confirmation_missing" if not live_confirmed else "delivery_failed"
            )
    if downstream_handoff:
        extra_payloads["downstream_handoff"] = downstream_handoff

    meta.finish()
    artifact_paths = _expected_artifacts(run_dir)
    if extra_payloads:
        artifact_paths.update({f"{name}_json": str(run_dir / f"{name}.json") for name in extra_payloads})

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
    task_record = {
        "task_id": f"task-{run_id}",
        "run_id": run_id,
        "preset": preset_name,
        "status": task_state,
        "artifacts": artifact_paths,
        "summary": f"{len(items)} items collected for {preset_name}",
        "status_reason": _unique(status_reasons),
        "observations": _downstream_observations(downstream_handoff),
    }

    try:
        post_state_context = build_execution_context(state_path, memory_path, preset_name)
    except Exception as exc:
        post_state_context = ExecutionContext(preset=preset_name)
        dependency_health["state"] = "failed"
        status_reasons.append("state_read_failed")
        errors.append(f"state_read_failed: {exc}")
        final_status = _final_status(dependency_health, status_reasons)
        task_state = {"ok": "done", "degraded": "needs_review", "failed": "failed"}[final_status]
        task_record["status"] = task_state
        task_record["status_reason"] = _unique(status_reasons)

    reservation_report = {
        "status": final_status,
        "status_reason": _unique(status_reasons),
        "run_meta": meta.to_dict(),
        "collected_items": [item.to_dict() for item in items],
    }
    try:
        operations_record = reserve_notification_outbox(
            operations_path,
            run_id,
            preset_name,
            reservation_report,
            artifact_paths,
        )
    except Exception as exc:
        dependency_health["operations"] = "degraded"
        status_reasons.append("operations_reservation_failed")
        errors.append(f"operations_reservation_failed: {exc}")
        final_status = _final_status(dependency_health, status_reasons)
        task_state = {"ok": "done", "degraded": "needs_review", "failed": "failed"}[final_status]
        task_record["status"] = task_state
        task_record["status_reason"] = _unique(status_reasons)
        operations_record = {
            "schema_version": meta.schema_version,
            "notification_id": f"note-{run_id}",
            "run_id": run_id,
            "preset": preset_name,
            "status": "failed",
            "error": "operations_reservation_failed",
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
            extra_payloads or None,
        )
    except Exception as exc:
        dependency_health["report"] = "failed"
        status_reasons.append("report_save_failed")
        errors.append(f"report_save_failed: {exc}")
        final_status = "failed"
        if operations_record.get("status") == "preparing":
            try:
                operations_record = transition_notification_outbox(
                    operations_path,
                    run_id,
                    "canceled",
                    "report_save_failed",
                )
            except Exception as outbox_exc:
                errors.append(f"operations_cancel_failed: {outbox_exc}")
                operations_record = {
                    **operations_record,
                    "status": "failed",
                    "error": "operations_cancel_failed",
                }
        task_record = _safe_task_update(
            state_path,
            run_id,
            preset_name,
            "failed",
            {},
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
            "artifacts": {},
            "taskstate_refs": [task_record],
            "memx_refs": [memx_record],
            "tracker_sync_refs": [tracker_event],
            "error": str(exc),
        }
        artifacts = {}
    else:
        if operations_record.get("status") == "preparing":
            try:
                operations_record = transition_notification_outbox(
                    operations_path,
                    run_id,
                    "pending",
                )
            except Exception as exc:
                dependency_health["operations"] = "degraded"
                status_reasons.append("operations_commit_failed")
                errors.append(f"operations_commit_failed: {exc}")
                final_status = _final_status(dependency_health, status_reasons)
                task_state = "needs_review"
                operations_record = {
                    **operations_record,
                    "status": "failed",
                    "error": "operations_commit_failed",
                }
        task_record = _safe_task_update(
            state_path,
            run_id,
            preset_name,
            task_state,
            artifacts,
            f"{len(items)} items collected for {preset_name}",
            _unique(status_reasons),
            dependency_health,
            status_reasons,
            errors,
            _downstream_observations(downstream_handoff),
        )
    return {
        "meta": meta.to_dict() | {
            "status": final_status,
            "status_reason": _unique(status_reasons),
        },
        "report": report_payload,
        "insight": insight_payload,
        "gate": gate_payload,
        "operations": operations_record,
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
    observations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        record = upsert_task_record(
            state_path,
            run_id,
            preset_name,
            status,
            artifacts,
            summary,
            _unique(status_reason),
            observations=observations,
        )
        if record is None:
            dependency_health["state"] = "failed"
            mutable_reasons.append("state_write_failed")
            errors.append("state_write_failed: lock acquisition timeout")
        return {
            "task_id": f"task-{run_id}",
            "run_id": run_id,
            "preset": preset_name,
            "status": status,
            "artifacts": artifacts,
            "summary": summary,
            "status_reason": _unique(status_reason),
            **({"observations": observations} if observations else {}),
        }
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
            **({"observations": observations} if observations else {}),
        }


def _disabled_payload(name: str, dependency_health: dict[str, str] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
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
    payload: dict[str, Any] = {
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


def _prepare_delivery(
    runtime: dict[str, Any],
    preset: dict[str, Any],
    delivery_mode_override: str | None,
    confirm_live: bool,
    run_id: str,
) -> tuple[str, TrackerBridgeTransport | None, str | None, bool]:
    mode = (
        delivery_mode_override
        or preset.get("downstream_handoff_mode")
        or runtime.get("downstream_handoff_mode", "dry_run")
    )
    if mode not in {"dry_run", "shadow", "live"}:
        mode = "dry_run"
    confirmed = confirm_live or os.environ.get("RAND_CONFIRM_LIVE_DELIVERY") == "1"
    if mode != "live":
        return mode, None, None, confirmed
    if not confirmed:
        return (
            mode,
            None,
            "live delivery requires --confirm-live or RAND_CONFIRM_LIVE_DELIVERY=1",
            False,
        )
    if not runtime.get("tracker_bridge_db_path") or not runtime.get("tracker_connection_id"):
        return mode, None, "tracker bridge DB path and connection ID are required", True
    return (
        mode,
        TrackerBridgeTransport(
            db_path=workspace_root() / runtime["tracker_bridge_db_path"],
            connection_id=str(runtime["tracker_connection_id"]),
            task_id=f"task-{run_id}",
        ),
        None,
        True,
    )

def _final_status(dependency_health: dict[str, str], status_reasons: list[str]) -> str:
    reasons = set(status_reasons)
    if (
        dependency_health.get("sources") == "failed"
        or dependency_health.get("state") == "failed"
        or dependency_health.get("report") == "failed"
        or "report_save_failed" in reasons
        or dependency_health.get("delivery") == "failed"
    ):
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


def _downstream_observations(handoff: dict[str, Any] | None) -> dict[str, Any] | None:
    if not handoff:
        return None
    return {
        "downstream_handoff": {
            "handoff_id": handoff.get("handoff_id"),
            "mode": handoff.get("status"),
            "delivery": handoff.get("delivery", {}),
        }
    }
