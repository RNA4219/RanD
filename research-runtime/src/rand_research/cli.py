from __future__ import annotations

import argparse

from rand_research.commands.operations import handle_operations_command, register_operations_commands
from rand_research.commands.review import handle_review_command, register_review_commands
from rand_research.commands.run import (
    handle_run_command,
    register_run_commands,
)
from rand_research.paths import workspace_root


def main() -> int:
    parser = argparse.ArgumentParser(prog="rand-research")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_run_commands(subparsers)
    register_operations_commands(subparsers)
    register_review_commands(subparsers)

    args = parser.parse_args()
    runtime_root = workspace_root()
    repo_root = runtime_root.parent

    run_exit_code = handle_run_command(args)
    if run_exit_code is not None:
        return run_exit_code
    if handle_operations_command(args, runtime_root, parser):
        return 0
    review_exit_code = handle_review_command(args, runtime_root, repo_root)
    if review_exit_code is not None:
        return review_exit_code

    parser.error(f"unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
