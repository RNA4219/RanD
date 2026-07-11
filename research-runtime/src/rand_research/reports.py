from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from rand_research.artifact_schema import (
    build_artifact_envelope,
    validate_artifact_payload,
    validate_manifest_checksums,
)
from rand_research.io_utils import atomic_write_text
from rand_research.models import SCHEMA_VERSION, NormalizedItem, RunMeta


def build_report_payload(
    meta: RunMeta,
    items: list[NormalizedItem],
    status: str,
    status_reason: list[str],
    dependency_health: dict[str, str],
    task_record: dict[str, Any],
    memx_record: dict[str, Any],
    tracker_event: dict[str, Any],
    gate_payload: dict[str, Any],
    pre_state_context: dict[str, Any],
    post_state_context: dict[str, Any],
    artifacts: dict[str, str],
    extra_payloads: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    operational_summary = build_operational_summary(items, dependency_health, gate_payload)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "status_reason": status_reason,
        "run_meta": meta.to_dict(),
        "operational_summary": operational_summary,
        "collected_items": [item.to_dict() for item in items],
        "state_context": {
            "before": pre_state_context,
            "after": post_state_context,
        },
        "dependency_health": dependency_health,
        "artifacts": artifacts,
        "taskstate_refs": [task_record],
        "memx_refs": [memx_record],
        "tracker_sync_refs": [tracker_event],
    }
    if extra_payloads:
        payload.update(extra_payloads)
    return payload


def build_operational_summary(
    items: list[NormalizedItem],
    dependency_health: dict[str, str],
    gate_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    seen_count = sum(1 for item in items if item.metadata.get("seen_before"))
    high_priority_count = sum(1 for item in items if item.high_priority)
    dependency_counts: dict[str, int] = {}
    for component_status in dependency_health.values():
        dependency_counts[component_status] = dependency_counts.get(component_status, 0) + 1

    gate_verdict_counts: dict[str, int] = {}
    for result in (gate_payload or {}).get("results", []):
        verdict = result.get("decision", {}).get("verdict", "unknown")
        gate_verdict_counts[verdict] = gate_verdict_counts.get(verdict, 0) + 1

    return {
        "item_count": len(items),
        "new_item_count": len(items) - seen_count,
        "seen_before_count": seen_count,
        "high_priority_count": high_priority_count,
        "source_count": len({item.source_name for item in items}),
        "dependency_status_counts": dependency_counts,
        "gate_verdict_counts": gate_verdict_counts,
    }


def legacy_save_run_outputs(
    run_dir: Path,
    meta: RunMeta,
    items: list[NormalizedItem],
    insight_payload: dict[str, Any],
    gate_payload: dict[str, Any],
    task_record: dict[str, Any],
    memx_record: dict[str, Any],
    tracker_event: dict[str, Any],
    pre_state_context: dict[str, Any],
    post_state_context: dict[str, Any],
    status: str,
    status_reason: list[str],
    dependency_health: dict[str, str],
    extra_payloads: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, str], dict[str, Any]]:
    run_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "report_md": run_dir / "report.md",
        "report_json": run_dir / "report.json",
        "insight_json": run_dir / "insight.json",
        "gate_json": run_dir / "gate.json",
        "meta_json": run_dir / "meta.json",
        "tracker_sync_json": run_dir / "tracker_sync.json",
        "memx_journal_json": run_dir / "memx_journal.json",
        "state_context_json": run_dir / "state_context.json",
    }
    if extra_payloads:
        for name in extra_payloads:
            paths[f"{name}_json"] = run_dir / f"{name}.json"
    artifacts = {key: str(path) for key, path in paths.items()}
    state_context = {
        "schema_version": SCHEMA_VERSION,
        "before": pre_state_context,
        "after": post_state_context,
    }
    report_payload = build_report_payload(
        meta,
        items,
        status,
        status_reason,
        dependency_health,
        task_record,
        memx_record,
        tracker_event,
        gate_payload,
        pre_state_context,
        post_state_context,
        artifacts,
        extra_payloads,
    )
    meta_payload = meta.to_dict() | {
        "status": status,
        "status_reason": status_reason,
        "dependency_health": dependency_health,
    }
    memx_payload = _wrap_single_record("entries", memx_record)
    tracker_payload = _wrap_single_record("events", tracker_event)
    paths["report_json"].write_text(json.dumps(report_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["insight_json"].write_text(json.dumps(insight_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["gate_json"].write_text(json.dumps(gate_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["meta_json"].write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["tracker_sync_json"].write_text(json.dumps(tracker_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["memx_journal_json"].write_text(json.dumps(memx_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["state_context_json"].write_text(json.dumps(state_context, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    for name, payload in (extra_payloads or {}).items():
        paths[f"{name}_json"].write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(render_markdown(meta, items, insight_payload, gate_payload, state_context, status, status_reason, dependency_health), encoding="utf-8")
    return artifacts, report_payload


def render_markdown(
    meta: RunMeta,
    items: list[NormalizedItem],
    insight_payload: dict[str, Any],
    gate_payload: dict[str, Any],
    state_context: dict[str, Any],
    status: str,
    status_reason: list[str],
    dependency_health: dict[str, str],
) -> str:
    before = state_context.get("before", {})
    after = state_context.get("after", {})
    operational_summary = build_operational_summary(items, dependency_health, gate_payload)
    lines = [
        f"# Research Report: {meta.preset}",
        "",
        f"- Schema Version: `{SCHEMA_VERSION}`",
        f"- Run ID: `{meta.run_id}`",
        f"- Status: `{status}`",
        f"- Status Reason: `{', '.join(status_reason) or 'none'}`",
        f"- Started: `{meta.started_at}`",
        f"- Finished: `{meta.finished_at or 'running'}`",
        f"- Items: `{operational_summary['item_count']}` total / `{operational_summary['new_item_count']}` new / `{operational_summary['seen_before_count']}` seen before",
        f"- High Priority Items: `{operational_summary['high_priority_count']}`",
        "",
        "## Dependency Health",
        "",
        *[f"- {name}: `{component_status}`" for name, component_status in sorted(dependency_health.items())],
        "",
        "## State Context",
        "",
        f"- Prior runs for preset: `{before.get('previous_run_count', 0)}`",
        f"- Known URLs before run: `{len(before.get('known_urls', []))}`",
        f"- Open tasks before run: `{len(before.get('open_tasks', []))}`",
        f"- Open tasks after run: `{len(after.get('open_tasks', []))}`",
        "",
        "## Top Items",
        "",
    ]
    for index, item in enumerate(items[:10], start=1):
        lines.extend(
            [
                f"### {index}. [{item.title}]({item.url})",
                f"- Source: `{item.source_name}`",
                f"- Kind: `{item.kind}`",
                f"- Priority: `{item.priority}`",
                f"- High Priority: `{item.high_priority}`",
                f"- Seen Before: `{item.metadata.get('seen_before', False)}`",
                f"- Published: `{item.published_at or 'unknown'}`",
                f"- Authors: {', '.join(item.authors) or 'unknown'}",
                f"- Summary: {item.summary or 'n/a'}",
                "",
            ]
        )
    lines.extend(
        [
            "## Insight Summary",
            "",
            f"- Status: `{insight_payload.get('status', 'unknown')}`",
            f"- Mode: `{insight_payload.get('mode', 'unknown')}`",
            f"- Result Count: `{len(insight_payload.get('results', []))}`",
            "",
            "## Gate Summary",
            "",
            f"- Status: `{gate_payload.get('status', 'unknown')}`",
            f"- Mode: `{gate_payload.get('mode', 'unknown')}`",
            f"- Result Count: `{len(gate_payload.get('results', []))}`",
            "",
        ]
    )
    return "\n".join(lines)


def _wrap_single_record(key: str, record: dict[str, Any]) -> dict[str, Any]:
    wrapped_record = dict(record)
    wrapped_record.setdefault("schema_version", SCHEMA_VERSION)
    return {
        "schema_version": SCHEMA_VERSION,
        key: [wrapped_record],
    }


def save_run_outputs(
    run_dir: Path,
    meta: RunMeta,
    items: list[NormalizedItem],
    insight_payload: dict[str, Any],
    gate_payload: dict[str, Any],
    task_record: dict[str, Any],
    memx_record: dict[str, Any],
    tracker_event: dict[str, Any],
    pre_state_context: dict[str, Any],
    post_state_context: dict[str, Any],
    status: str,
    status_reason: list[str],
    dependency_health: dict[str, str],
    extra_payloads: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Stage every artifact and publish the run directory in one rename."""
    final_dir = Path(run_dir)
    parent = final_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    if final_dir.exists():
        raise FileExistsError(f"run directory already exists: {final_dir}")
    staging_dir = parent / f".staging-{final_dir.name}-{uuid4().hex}"
    staging_dir.mkdir()

    names = {
        "report_md": "report.md",
        "report_json": "report.json",
        "insight_json": "insight.json",
        "gate_json": "gate.json",
        "meta_json": "meta.json",
        "tracker_sync_json": "tracker_sync.json",
        "memx_journal_json": "memx_journal.json",
        "state_context_json": "state_context.json",
        "manifest_json": "manifest.json",
    }
    for name in extra_payloads or {}:
        names[f"{name}_json"] = f"{name}.json"
    final_paths = {key: final_dir / filename for key, filename in names.items()}
    write_paths = {key: staging_dir / filename for key, filename in names.items()}
    artifacts = {key: str(path) for key, path in final_paths.items()}
    state_context = {
        "schema_version": SCHEMA_VERSION,
        "before": pre_state_context,
        "after": post_state_context,
    }
    report_payload = build_report_payload(
        meta,
        items,
        status,
        status_reason,
        dependency_health,
        task_record,
        memx_record,
        tracker_event,
        gate_payload,
        pre_state_context,
        post_state_context,
        artifacts,
        extra_payloads,
    )
    meta_payload = meta.to_dict() | {
        "status": status,
        "status_reason": status_reason,
        "dependency_health": dependency_health,
    }
    payloads = {
        "report_json": report_payload,
        "insight_json": insight_payload,
        "gate_json": gate_payload,
        "meta_json": meta_payload,
        "tracker_sync_json": _wrap_single_record("events", tracker_event),
        "memx_journal_json": _wrap_single_record("entries", memx_record),
        "state_context_json": state_context,
        **{f"{name}_json": payload for name, payload in (extra_payloads or {}).items()},
    }

    source_refs = sorted({item.url for item in items if item.url})
    created_at = meta.finished_at or meta.started_at
    enveloped_payloads: dict[str, dict[str, Any]] = {}
    for key, payload in payloads.items():
        artifact_type = key.removesuffix("_json")
        allowed_uses = (
            ["review", "tracker_issue_creation"]
            if artifact_type == "downstream_handoff"
            else ["review", "analysis"]
        )
        enveloped = build_artifact_envelope(
            payload,
            artifact_id=f"rand:artifact:{meta.run_id}:{artifact_type}",
            artifact_type=artifact_type,
            created_at=created_at,
            input_refs=[f"rand:run:{meta.run_id}"],
            source_refs=source_refs,
            downstream_allowed_uses=allowed_uses,
        )
        validation = validate_artifact_payload(enveloped, artifact_type)
        if validation["status"] != "ok":
            _cleanup_staging_directory(staging_dir, parent)
            raise ValueError(f"{artifact_type} artifact validation failed: {validation['issues']}")
        enveloped_payloads[key] = enveloped
    payloads = enveloped_payloads
    report_payload = payloads["report_json"]
    try:
        for key, payload in payloads.items():
            atomic_write_text(
                write_paths[key],
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            )
        atomic_write_text(
            write_paths["report_md"],
            render_markdown(
                meta,
                items,
                insight_payload,
                gate_payload,
                state_context,
                status,
                status_reason,
                dependency_health,
            ),
        )
        manifest_entries = []
        for key, path in write_paths.items():
            if key == "manifest_json":
                continue
            content = path.read_bytes()
            manifest_entries.append(
                {
                    "artifact": key,
                    "path": str(final_paths[key]),
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                }
            )
        manifest = build_artifact_envelope(
            {
                "run_id": meta.run_id,
                "status": "committed",
                "artifacts": manifest_entries,
            },
            artifact_id=f"rand:artifact:{meta.run_id}:manifest",
            artifact_type="manifest",
            created_at=created_at,
            input_refs=[f"rand:run:{meta.run_id}"],
            source_refs=source_refs,
            downstream_allowed_uses=["integrity_verification", "review"],
        )
        manifest_validation = validate_artifact_payload(manifest, "manifest")
        checksum_issues = validate_manifest_checksums(manifest, staging_dir)
        if manifest_validation["status"] != "ok" or checksum_issues:
            raise ValueError(
                f"manifest validation failed: {manifest_validation['issues'] + checksum_issues}"
            )
        atomic_write_text(
            write_paths["manifest_json"],
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )
        os.replace(staging_dir, final_dir)
        return artifacts, report_payload
    except Exception:
        _cleanup_staging_directory(staging_dir, parent)
        raise


def _cleanup_staging_directory(staging_dir: Path, expected_parent: Path) -> None:
    try:
        resolved = staging_dir.resolve()
        parent = expected_parent.resolve()
    except OSError:
        return
    if resolved.parent != parent or not resolved.name.startswith(".staging-"):
        return
    shutil.rmtree(resolved, ignore_errors=True)
