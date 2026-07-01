from __future__ import annotations

import argparse
from pathlib import Path

from rand_research.commands.common import print_json
from rand_research.config import load_runtime_config
from rand_research.metrics import collect_metrics
from rand_research.operations import build_outbox_plan, mark_notification_attempt, pending_resend_payloads, plan_replay
from rand_research.pilot_health import evaluate_pilot_readiness
from rand_research.pilot_snapshot import build_pilot_snapshot, write_pilot_snapshot


def register_operations_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    subparsers.add_parser("metrics")
    subparsers.add_parser("pilot-check")

    replay_parser = subparsers.add_parser("replay-plan")
    replay_parser.add_argument("--task-id", default=None)
    replay_parser.add_argument("--trace-id", default=None)

    resend_parser = subparsers.add_parser("resend-pending")
    resend_parser.add_argument("--limit", type=int, default=10)

    outbox_parser = subparsers.add_parser("outbox-plan")
    outbox_parser.add_argument("--limit", type=int, default=20)

    snapshot_parser = subparsers.add_parser("pilot-snapshot")
    snapshot_parser.add_argument("--out", default=None)
    snapshot_parser.add_argument("--outbox-limit", type=int, default=20)
    snapshot_parser.add_argument("--dry-run", action="store_true")

    mark_parser = subparsers.add_parser("mark-notification")
    mark_parser.add_argument("--notification-id", required=True)
    mark_parser.add_argument("--status", required=True, choices=["pending", "sent", "failed", "duplicate_suppressed"])
    mark_parser.add_argument("--error", default=None)


def handle_operations_command(args: argparse.Namespace, runtime_root: Path, parser: argparse.ArgumentParser) -> bool:
    if args.command == "metrics":
        print_json(collect_metrics(runtime_root))
        return True
    if args.command == "pilot-check":
        print_json(evaluate_pilot_readiness(runtime_root))
        return True
    if args.command == "replay-plan":
        if not args.task_id and not args.trace_id:
            parser.error("replay-plan requires --task-id or --trace-id")
        runtime = load_runtime_config()
        print_json(
            plan_replay(
                runtime_root / runtime["state_path"],
                runtime_root / runtime.get("operations_state_path", "state/operations-state.json"),
                args.task_id,
                args.trace_id,
            )
        )
        return True
    if args.command == "resend-pending":
        runtime = load_runtime_config()
        print_json(
            pending_resend_payloads(
                runtime_root / runtime.get("operations_state_path", "state/operations-state.json"),
                args.limit,
            )
        )
        return True
    if args.command == "outbox-plan":
        runtime = load_runtime_config()
        print_json(
            build_outbox_plan(
                runtime_root / runtime.get("operations_state_path", "state/operations-state.json"),
                args.limit,
            )
        )
        return True
    if args.command == "pilot-snapshot":
        if args.dry_run:
            print_json(build_pilot_snapshot(runtime_root, args.outbox_limit))
        else:
            print_json(
                write_pilot_snapshot(
                    runtime_root,
                    Path(args.out) if args.out else None,
                    args.outbox_limit,
                )
            )
        return True
    if args.command == "mark-notification":
        runtime = load_runtime_config()
        print_json(
            mark_notification_attempt(
                runtime_root / runtime.get("operations_state_path", "state/operations-state.json"),
                args.notification_id,
                args.status,
                args.error,
            )
        )
        return True
    return False
