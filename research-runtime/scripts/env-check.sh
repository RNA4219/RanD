#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$script_dir/.." && pwd)"

export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
python -m rand_research.cli env-check
