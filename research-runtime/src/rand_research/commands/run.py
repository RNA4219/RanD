from __future__ import annotations

import argparse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from rand_research.commands.common import print_json
from rand_research.config import load_heartbeat_config, load_schedule
from rand_research.integrations import check_dependencies
from rand_research.pipeline import run_once


def select_preset_by_time() -> str:
    config = load_heartbeat_config()
    timezone_name = config.get("timezone", "Asia/Tokyo")
    now = datetime.now(ZoneInfo(timezone_name))
    current_hour = now.hour

    for rule in config.get("rules", []):
        if current_hour in rule.get("hours", []):
            return rule["preset"]
    return config.get("default_preset", "paper_arxiv_ai_recent")


def build_summary(report: dict, preset: str) -> dict:
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


def register_run_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    run_once_parser = subparsers.add_parser("run-once")
    run_once_parser.add_argument("--preset", required=True)
    run_once_parser.add_argument("--max-items", type=int, default=0)
    _add_delivery_arguments(run_once_parser)

    subparsers.add_parser("run-schedule")
    subparsers.add_parser("env-check")

    heartbeat_parser = subparsers.add_parser("heartbeat")
    heartbeat_parser.add_argument("--preset", default=None, help="Preset to run (auto-select if not specified)")
    heartbeat_parser.add_argument("--max-items", type=int, default=5, help="Max items to collect")
    heartbeat_parser.add_argument("--dry-run", action="store_true", help="Show what would run without executing")
    heartbeat_parser.add_argument("--summary-only", action="store_true", help="Output only summary for Misskey")
    _add_delivery_arguments(heartbeat_parser)


def _add_delivery_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--delivery-mode",
        choices=["dry_run", "shadow", "live"],
        default=None,
    )
    parser.add_argument("--confirm-live", action="store_true")

def handle_run_command(args: argparse.Namespace) -> int | None:
    if args.command == "run-once":
        result = run_once(
            args.preset,
            args.max_items or None,
            getattr(args, "delivery_mode", None),
            getattr(args, "confirm_live", False),
        )
        print_json(result["report"])
        return status_exit_code(result["report"].get("status"))
    if args.command == "run-schedule":
        schedule = load_schedule()
        results = []
        for job in schedule.get("jobs", []):
            results.append({"job": job["name"], "result": run_once(job["preset"])["report"]})
        print_json(results)
        statuses = [entry["result"].get("status") for entry in results]
        if "failed" in statuses:
            return 1
        if "degraded" in statuses:
            return 2
        return 0
    if args.command == "env-check":
        print_json(check_dependencies())
        return 0
    if args.command == "heartbeat":
        preset = args.preset or select_preset_by_time()

        if args.dry_run:
            print_json(
                {
                    "dry_run": True,
                    "preset": preset,
                    "max_items": args.max_items,
                    "timezone": load_heartbeat_config().get("timezone", "Asia/Tokyo"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            return 0

        result = run_once(
            preset,
            args.max_items,
            getattr(args, "delivery_mode", None),
            getattr(args, "confirm_live", False),
        )
        print_json(build_summary(result["report"], preset) if args.summary_only else result["report"])
        return status_exit_code(result["report"].get("status"))
    return None


def status_exit_code(status: str | None) -> int:
    if status == "ok":
        return 0
    if status == "degraded":
        return 2
    return 1
