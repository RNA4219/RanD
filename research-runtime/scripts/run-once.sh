#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$script_dir/.." && pwd)"
preset="${1:-paper_arxiv_ai_recent}"
max_items="${2:-0}"

export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"

args=(-m rand_research.cli run-once --preset "$preset")
if [[ "$max_items" != "0" ]]; then
  args+=(--max-items "$max_items")
fi

python "${args[@]}"
