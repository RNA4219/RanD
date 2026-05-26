#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
installer_dir="$script_dir/r-and-d-agent-installer"
install_script="$installer_dir/scripts/install.ps1"
status_script="$installer_dir/scripts/status.ps1"

if [[ ! -f "$install_script" ]]; then
  echo "installer script not found: $install_script" >&2
  exit 1
fi

if ! command -v pwsh >/dev/null 2>&1; then
  echo "pwsh is required on macOS/Linux to run the PowerShell installer." >&2
  exit 1
fi

mode="auto"
args=()
for arg in "$@"; do
  case "$arg" in
    --force) args+=("-Force") ;;
    --skip-optional) args+=("-SkipOptional") ;;
    --local) mode="local" ;;
    --remote) mode="remote" ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

pwsh -NoProfile -ExecutionPolicy Bypass -File "$install_script" -Mode "$mode" "${args[@]}"
echo
echo "status:"
pwsh -NoProfile -ExecutionPolicy Bypass -File "$status_script"
