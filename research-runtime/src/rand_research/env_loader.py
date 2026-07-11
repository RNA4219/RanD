from __future__ import annotations

import os
import sys
from typing import Any

from rand_research.config import load_runtime_config
from rand_research.paths import installer_root, workspace_root


def ensure_repo_paths() -> None:
    repo_map = {
        "insight-agent": installer_root() / "insight-agent",
        "experiment-gate": installer_root() / "experiment-gate",
        "agent-taskstate": installer_root() / "agent-taskstate",
        "open_deep_research": installer_root() / "open_deep_research" / "src",
        "tracker-bridge-materials": installer_root() / "tracker-bridge-materials",
        "memx-resolver": installer_root() / "memx-resolver",
    }
    for path in repo_map.values():
        if path.exists():
            sys.path.insert(0, str(path))


def load_env_from_peer_repos() -> dict[str, Any]:
    codex_dev_root = workspace_root().parent.parent
    candidates = [
        codex_dev_root / "experiment-gate" / ".env",
        codex_dev_root / "insight-agent" / ".env",
        codex_dev_root / "Roadmap-Design-Skill" / ".env",
        codex_dev_root / "pulse-kestra" / "bridge" / ".env",
    ]
    loaded_files: list[str] = []
    loaded_keys: list[str] = []
    for path in candidates:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if not key or key in os.environ:
                continue
            os.environ[key] = value
            loaded_keys.append(key)
        loaded_files.append(str(path))
    provider_report = _prefer_runtime_providers()
    timeout_report = _stretch_runtime_timeouts()
    return {
        "loaded_files": loaded_files,
        "loaded_keys": sorted(set(loaded_keys)),
        "provider_report": provider_report,
        "timeout_report": timeout_report,
    }


def _prefer_runtime_providers() -> dict[str, Any]:
    sequence: list[str] = []
    if os.environ.get("OPENROUTER_API_KEY"):
        sequence.append("openrouter")
    if os.environ.get("DASHSCOPE_API_KEY"):
        sequence.append("alibaba")
    if sequence:
        os.environ["LLM_PROVIDER"] = sequence[0]
        os.environ["LLM_PROVIDER_SEQUENCE"] = ",".join(sequence)
    return {
        "selected_provider": os.environ.get("LLM_PROVIDER", ""),
        "provider_sequence": os.environ.get("LLM_PROVIDER_SEQUENCE", ""),
    }


def _stretch_runtime_timeouts() -> dict[str, Any]:
    runtime = load_runtime_config()
    llm_timeout = str(max(int(os.environ.get("LLM_TIMEOUT_SECONDS", "0") or 0), int(runtime.get("llm_timeout_seconds", 600))))
    llm_retries = str(max(int(os.environ.get("LLM_MAX_RETRIES", "0") or 0), int(runtime.get("llm_max_retries", 4))))
    llm_backoff = str(max(float(os.environ.get("LLM_RETRY_BACKOFF_SECONDS", "0") or 0), float(runtime.get("llm_retry_backoff_seconds", 2.0))))
    os.environ["LLM_TIMEOUT_SECONDS"] = llm_timeout
    os.environ["LLM_MAX_RETRIES"] = llm_retries
    os.environ["LLM_RETRY_BACKOFF_SECONDS"] = llm_backoff
    return {
        "llm_timeout_seconds": llm_timeout,
        "llm_max_retries": llm_retries,
        "llm_retry_backoff_seconds": llm_backoff,
    }
