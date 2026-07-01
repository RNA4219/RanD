from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from rand_research.config import load_heartbeat_config, load_runtime_config, load_schedule
from rand_research.integrations import check_dependencies
from rand_research.metrics import collect_metrics
from rand_research.operations import mark_notification_attempt, pending_resend_payloads, plan_replay
from rand_research.paths import workspace_root
from rand_research.pipeline import run_once
from rand_research.review_tools import (
    build_shadow_eval_template,
    build_tracker_review,
    generate_task_seed_drafts,
    write_payload_or_print,
)


def _select_preset_by_time() -> str:
    config = load_heartbeat_config()
    timezone_name = config.get("timezone", "Asia/Tokyo")
    now = datetime.now(ZoneInfo(timezone_name))
    current_hour = now.hour

    for rule in config.get("rules", []):
        if current_hour in rule.get("hours", []):
            return rule["preset"]
    return config.get("default_preset", "paper_arxiv_ai_recent")


def _build_summary(report: dict, preset: str) -> dict:
    items = report.get("collected_items", [])
    state_ctx = report.get("state_context", {})
    before_count = len(state_ctx.get("before", {}).get("open_tasks", []))
    after_count = len(state_ctx.get("after", {}).get("open_tasks", []))

    return {
        "preset": preset,
        "status": report.get("status", "unknown"),
        "status_reason": report.get("status_reason", []),
        "collected_count": len(items),
        "open_tasks_before": before_count,
        "open_tasks_after": after_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "top_items": [
            {"title": item.get("title", ""), "url": item.get("url", "")}
            for item in items[:3]
            if item.get("title")
        ],
    }


def _resolve_path(value: str, base: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def main() -> None:
    parser = argparse.ArgumentParser(prog="rand-research")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_once_parser = subparsers.add_parser("run-once")
    run_once_parser.add_argument("--preset", required=True)
    run_once_parser.add_argument("--max-items", type=int, default=0)

    subparsers.add_parser("run-schedule")
    subparsers.add_parser("env-check")
    subparsers.add_parser("metrics")

    replay_parser = subparsers.add_parser("replay-plan")
    replay_parser.add_argument("--task-id", default=None)
    replay_parser.add_argument("--trace-id", default=None)

    resend_parser = subparsers.add_parser("resend-pending")
    resend_parser.add_argument("--limit", type=int, default=10)

    mark_parser = subparsers.add_parser("mark-notification")
    mark_parser.add_argument("--notification-id", required=True)
    mark_parser.add_argument("--status", required=True, choices=["pending", "sent", "failed", "duplicate_suppressed"])
    mark_parser.add_argument("--error", default=None)

    shadow_eval_parser = subparsers.add_parser("shadow-eval-template")
    shadow_eval_parser.add_argument("--run-dir", required=True)
    shadow_eval_parser.add_argument("--format", choices=["json", "csv"], default="json")
    shadow_eval_parser.add_argument("--out", default=None)

    tracker_review_parser = subparsers.add_parser("tracker-review")
    tracker_review_parser.add_argument("--path", required=True)
    tracker_review_parser.add_argument("--out", default=None)

    task_seed_parser = subparsers.add_parser("generate-task-seeds")
    task_seed_parser.add_argument("--handoff", required=True)
    task_seed_parser.add_argument("--out-dir", default="docs/tasks/generated")
    task_seed_parser.add_argument("--write", action="store_true", help="Write files; default is dry-run JSON output")

    heartbeat_parser = subparsers.add_parser("heartbeat")
    heartbeat_parser.add_argument("--preset", default=None, help="Preset to run (auto-select if not specified)")
    heartbeat_parser.add_argument("--max-items", type=int, default=5, help="Max items to collect")
    heartbeat_parser.add_argument("--dry-run", action="store_true", help="Show what would run without executing")
    heartbeat_parser.add_argument("--summary-only", action="store_true", help="Output only summary for Misskey")

    args = parser.parse_args()
    if args.command == "run-once":
        result = run_once(args.preset, args.max_items or None)
        print(json.dumps(result["report"], ensure_ascii=False, indent=2))
        return
    if args.command == "run-schedule":
        schedule = load_schedule()
        results = []
        for job in schedule.get("jobs", []):
            results.append({"job": job["name"], "result": run_once(job["preset"])["report"]})
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return
    if args.command == "env-check":
        print(json.dumps(check_dependencies(), ensure_ascii=False, indent=2))
        return
    if args.command == "metrics":
        print(json.dumps(collect_metrics(workspace_root()), ensure_ascii=False, indent=2))
        return
    if args.command == "replay-plan":
        if not args.task_id and not args.trace_id:
            parser.error("replay-plan requires --task-id or --trace-id")
        runtime = load_runtime_config()
        output = plan_replay(
            workspace_root() / runtime["state_path"],
            workspace_root() / runtime.get("operations_state_path", "state/operations-state.json"),
            args.task_id,
            args.trace_id,
        )
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return
    if args.command == "resend-pending":
        runtime = load_runtime_config()
        output = pending_resend_payloads(
            workspace_root() / runtime.get("operations_state_path", "state/operations-state.json"),
            args.limit,
        )
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return
    if args.command == "mark-notification":
        runtime = load_runtime_config()
        output = mark_notification_attempt(
            workspace_root() / runtime.get("operations_state_path", "state/operations-state.json"),
            args.notification_id,
            args.status,
            args.error,
        )
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return
    if args.command == "shadow-eval-template":
        payload = build_shadow_eval_template(_resolve_path(args.run_dir, workspace_root()))
        content = write_payload_or_print(
            payload,
            (_resolve_path(args.out, workspace_root()) if args.out else None),
            args.format,
        )
        print(content)
        return
    if args.command == "tracker-review":
        payload = build_tracker_review(_resolve_path(args.path, workspace_root()))
        content = write_payload_or_print(payload, _resolve_path(args.out, workspace_root()) if args.out else None)
        print(content)
        return
    if args.command == "generate-task-seeds":
        payload = generate_task_seed_drafts(
            _resolve_path(args.handoff, workspace_root()),
            _resolve_path(args.out_dir, workspace_root().parent),
            dry_run=not args.write,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if args.command == "heartbeat":
        preset = args.preset or _select_preset_by_time()

        if args.dry_run:
            output = {
                "dry_run": True,
                "preset": preset,
                "max_items": args.max_items,
                "timezone": load_heartbeat_config().get("timezone", "Asia/Tokyo"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return

        result = run_once(preset, args.max_items)

        if args.summary_only:
            summary = _build_summary(result["report"], preset)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(result["report"], ensure_ascii=False, indent=2))
        return


if __name__ == "__main__":
    main()
