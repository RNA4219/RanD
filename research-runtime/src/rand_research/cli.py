from __future__ import annotations

import argparse

from rand_research.commands.operations import handle_operations_command, register_operations_commands
from rand_research.commands.review import handle_review_command, register_review_commands
from rand_research.commands.run import (
    build_summary as _build_summary,
    handle_run_command,
    register_run_commands,
    select_preset_by_time as _select_preset_by_time,
)
from rand_research.paths import workspace_root


def main() -> None:
    parser = argparse.ArgumentParser(prog="rand-research")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_run_commands(subparsers)
    register_operations_commands(subparsers)
    register_review_commands(subparsers)

    args = parser.parse_args()
    runtime_root = workspace_root()
    repo_root = runtime_root.parent

    if handle_run_command(args):
        return
    if handle_operations_command(args, runtime_root, parser):
        return
    if handle_review_command(args, runtime_root, repo_root):
        return

    parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
