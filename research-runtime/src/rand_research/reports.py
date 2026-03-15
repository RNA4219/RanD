from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rand_research.models import NormalizedItem, RunMeta, SCHEMA_VERSION


def build_report_payload(
    meta: RunMeta,
    items: list[NormalizedItem],
    status: str,
    status_reason: list[str],
    dependency_health: dict[str, str],
    task_record: dict[str, Any],
    memx_record: dict[str, Any],
    tracker_event: dict[str, Any],
    pre_state_context: dict[str, Any],
    post_state_context: dict[str, Any],
    artifacts: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "status_reason": status_reason,
        "run_meta": meta.to_dict(),
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
        pre_state_context,
        post_state_context,
        artifacts,
    )
    meta_payload = meta.to_dict() | {
        "status": status,
        "status_reason": status_reason,
        "dependency_health": dependency_health,
    }
    paths["report_json"].write_text(json.dumps(report_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["insight_json"].write_text(json.dumps(insight_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["gate_json"].write_text(json.dumps(gate_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["meta_json"].write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["tracker_sync_json"].write_text(json.dumps(tracker_event, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["memx_journal_json"].write_text(json.dumps(memx_record, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["state_context_json"].write_text(json.dumps(state_context, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
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
    lines = [
        f"# Research Report: {meta.preset}",
        "",
        f"- Schema Version: `{SCHEMA_VERSION}`",
        f"- Run ID: `{meta.run_id}`",
        f"- Status: `{status}`",
        f"- Status Reason: `{', '.join(status_reason) or 'none'}`",
        f"- Started: `{meta.started_at}`",
        f"- Finished: `{meta.finished_at or 'running'}`",
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
