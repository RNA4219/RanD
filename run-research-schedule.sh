#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runtime_dir="$script_dir/research-runtime"

exec "$runtime_dir/scripts/run-schedule.sh"
