from __future__ import annotations

import argparse
import json

from rand_research.config import load_schedule
from rand_research.integrations import check_dependencies
from rand_research.pipeline import run_once


def main() -> None:
    parser = argparse.ArgumentParser(prog="rand-research")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_once_parser = subparsers.add_parser("run-once")
    run_once_parser.add_argument("--preset", required=True)
    run_once_parser.add_argument("--max-items", type=int, default=0)

    subparsers.add_parser("run-schedule")
    subparsers.add_parser("env-check")

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


if __name__ == "__main__":
    main()
