#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runtime_dir="$script_dir/research-runtime"
preset="${1:-paper_arxiv_ai_recent}"

exec "$runtime_dir/scripts/run-once.sh" "$preset"
