from __future__ import annotations

import argparse
from pathlib import Path

from rand_research.commands.common import print_json, resolve_path
from rand_research.artifact_schema import validate_artifact_path
from rand_research.review_tools import (
    build_shadow_eval_template,
    build_tracker_review,
    generate_task_seed_drafts,
    write_payload_or_print,
)


def register_review_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
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

    validate_parser = subparsers.add_parser("validate-artifact")
    validate_parser.add_argument("--path", required=True)
    validate_parser.add_argument("--type", default=None)


def handle_review_command(args: argparse.Namespace, runtime_root: Path, repo_root: Path) -> bool:
    if args.command == "shadow-eval-template":
        payload = build_shadow_eval_template(resolve_path(args.run_dir, runtime_root))
        content = write_payload_or_print(
            payload,
            (resolve_path(args.out, runtime_root) if args.out else None),
            args.format,
        )
        print(content)
        return True
    if args.command == "tracker-review":
        payload = build_tracker_review(resolve_path(args.path, runtime_root))
        content = write_payload_or_print(payload, resolve_path(args.out, runtime_root) if args.out else None)
        print(content)
        return True
    if args.command == "generate-task-seeds":
        print_json(
            generate_task_seed_drafts(
                resolve_path(args.handoff, runtime_root),
                resolve_path(args.out_dir, repo_root),
                dry_run=not args.write,
            )
        )
        return True
    if args.command == "validate-artifact":
        print_json(validate_artifact_path(resolve_path(args.path, runtime_root), args.type))
        return True
    return False
