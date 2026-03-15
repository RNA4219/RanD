from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rand_research.models import NormalizedItem, RunMeta


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
) -> dict[str, str]:
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
    state_context = {
        "before": pre_state_context,
        "after": post_state_context,
    }
    paths["report_json"].write_text(
        json.dumps(
            {
                "run_meta": meta.to_dict(),
                "collected_items": [item.to_dict() for item in items],
                "state_context": state_context,
                "taskstate_refs": [task_record],
                "memx_refs": [memx_record],
                "tracker_sync_refs": [tracker_event],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    paths["insight_json"].write_text(json.dumps(insight_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["gate_json"].write_text(json.dumps(gate_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["meta_json"].write_text(json.dumps(meta.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    paths["tracker_sync_json"].write_text(json.dumps(tracker_event, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["memx_journal_json"].write_text(json.dumps(memx_record, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["state_context_json"].write_text(json.dumps(state_context, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(render_markdown(meta, items, insight_payload, gate_payload, state_context), encoding="utf-8")
    return {key: str(path) for key, path in paths.items()}


def render_markdown(
    meta: RunMeta,
    items: list[NormalizedItem],
    insight_payload: dict[str, Any],
    gate_payload: dict[str, Any],
    state_context: dict[str, Any],
) -> str:
    before = state_context.get("before", {})
    after = state_context.get("after", {})
    lines = [
        f"# Research Report: {meta.preset}",
        "",
        f"- Run ID: `{meta.run_id}`",
        f"- Started: `{meta.started_at}`",
        f"- Finished: `{meta.finished_at or 'running'}`",
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
            f"- Mode: `{insight_payload.get('mode', 'unknown')}`",
            f"- Result Count: `{len(insight_payload.get('results', []))}`",
            "",
            "## Gate Summary",
            "",
            f"- Mode: `{gate_payload.get('mode', 'unknown')}`",
            f"- Result Count: `{len(gate_payload.get('results', []))}`",
            "",
        ]
    )
    return "\n".join(lines)
