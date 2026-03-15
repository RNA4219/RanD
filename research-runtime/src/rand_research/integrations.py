from __future__ import annotations

import importlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from rand_research.config import load_runtime_config
from rand_research.models import NormalizedItem, SCHEMA_VERSION
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


def build_insight_payload(item: NormalizedItem) -> dict[str, Any]:
    content = "\n".join(
        [
            f"Title: {item.title}",
            f"URL: {item.url}",
            f"Published: {item.published_at or 'unknown'}",
            f"Authors: {', '.join(item.authors) or 'unknown'}",
            f"Summary: {item.summary}",
            "Claims:",
            *[f"- {claim}" for claim in item.claims],
            "Evidence:",
            *[f"- {evidence}" for evidence in item.evidence],
        ]
    )
    return {
        "mode": "insight",
        "request_id": item.id,
        "sources": [
            {
                "source_id": item.id,
                "source_type": "text",
                "title": item.title,
                "content": content,
                "metadata": {
                    "url": item.url,
                    "published_at": item.published_at,
                },
            }
        ],
    }


def run_insight(items: list[NormalizedItem]) -> dict[str, Any]:
    ensure_repo_paths()
    load_env_from_peer_repos()
    try:
        insight_core = importlib.import_module("insight_core")
        results = []
        for item in items:
            payload = build_insight_payload(item)
            results.append(insight_core.run(request_dict=payload))
        status = _aggregate_nested_status(results)
        return {
            "schema_version": SCHEMA_VERSION,
            "status": status,
            "mode": "insight-agent",
            "results": results,
            "error": None if status == "ok" else _summarize_nested_failures("insight", results),
        }
    except Exception as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "degraded",
            "mode": "fallback",
            "results": [_fallback_insight(item) for item in items],
            "error": str(exc),
        }


def run_gate(items: list[NormalizedItem], dependency_health: dict[str, str]) -> dict[str, Any]:
    ensure_repo_paths()
    load_env_from_peer_repos()
    targets = [item for item in items if item.high_priority][:3]
    if not targets:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "ok",
            "mode": "skipped",
            "results": [],
            "error": None,
            "dependency_health": dependency_health,
        }
    try:
        experiment_gate = importlib.import_module("experiment_gate")
        results = []
        for item in targets:
            request = experiment_gate.GateRequest(
                request_id=item.id,
                hypothesis=f"{item.title} should be evaluated as a small PoC candidate.",
                poc_spec=experiment_gate.PocSpec(
                    objective=f"Verify whether {item.title} has practical follow-up value.",
                    problem=item.summary or item.title,
                    target_user_or_context="RanD daily research watch",
                    success_metrics=["Actionable follow-up identified"],
                    failure_or_abort_criteria=["No meaningful differentiator found"],
                    minimum_scope="Read the item, summarize it, and define one small next step.",
                    non_goals=["Production rollout"],
                    required_inputs_or_tools=[item.url],
                    validation_plan="Collect evidence and compare novelty, feasibility, and impact.",
                ),
                evidence_bundle=experiment_gate.EvidenceBundle(
                    claims=item.claims,
                    sources=[item.url],
                    gaps=["Full manual review not completed yet"],
                ),
                decision_context=(
                    "Daily AI research watch. Dependency health: "
                    + ", ".join(f"{name}={status}" for name, status in sorted(dependency_health.items()))
                ),
            )
            result = experiment_gate.run_gate(request=request).model_dump()
            result["dependency_health"] = dependency_health
            results.append(result)
        status = _aggregate_nested_status(results)
        return {
            "schema_version": SCHEMA_VERSION,
            "status": status,
            "mode": "experiment-gate",
            "results": results,
            "error": None if status == "ok" else _summarize_nested_failures("gate", results),
            "dependency_health": dependency_health,
        }
    except Exception as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "degraded",
            "mode": "fallback",
            "results": [_fallback_gate(item, dependency_health) for item in targets],
            "error": str(exc),
            "dependency_health": dependency_health,
        }


def write_memx_journal(path: Path, run_id: str, preset: str, items: list[NormalizedItem], artifacts: dict[str, str]) -> dict[str, Any]:
    payload = _load_log(path, "entries")
    entry = {
        "schema_version": SCHEMA_VERSION,
        "entry_id": f"memx-{run_id}",
        "scope": f"rand:{preset}",
        "recorded_at": datetime.utcnow().isoformat() + "Z",
        "summary": f"{len(items)} items collected",
        "sources": [item.url for item in items[:10]],
        "artifacts": artifacts,
        "status": "ok",
        "error": None,
    }
    payload["entries"].append(entry)
    _write_json(path, payload)
    return entry


def write_tracker_sync(path: Path, run_id: str, preset: str, items: list[NormalizedItem], gate_payload: dict[str, Any]) -> dict[str, Any]:
    payload = _load_log(path, "events")
    event = {
        "schema_version": SCHEMA_VERSION,
        "sync_id": f"sync-{run_id}",
        "recorded_at": datetime.utcnow().isoformat() + "Z",
        "preset": preset,
        "items": [
            {
                "title": item.title,
                "url": item.url,
                "kind": item.kind,
                "priority": item.priority,
            }
            for item in items[:5]
        ],
        "gate_recommendations": [
            {
                "request_id": result.get("run", {}).get("request_id"),
                "verdict": result.get("decision", {}).get("verdict"),
                "recommended_action": result.get("next_step", {}).get("recommended_action"),
                "dependency_health": result.get("dependency_health", gate_payload.get("dependency_health", {})),
            }
            for result in gate_payload.get("results", [])
        ],
        "status": "ok",
        "error": None,
    }
    payload["events"].append(event)
    _write_json(path, payload)
    return event


def check_dependencies() -> dict[str, Any]:
    ensure_repo_paths()
    env_report = load_env_from_peer_repos()
    report: dict[str, Any] = {}
    modules = {
        "open_deep_research": ("open_deep_research", installer_root() / "open_deep_research"),
        "insight_agent": ("insight_core", installer_root() / "insight-agent"),
        "experiment_gate": ("experiment_gate", installer_root() / "experiment-gate"),
        "agent_taskstate": (None, installer_root() / "agent-taskstate"),
        "memx_resolver": (None, installer_root() / "memx-resolver"),
        "tracker_bridge_materials": (None, installer_root() / "tracker-bridge-materials"),
    }
    for key, data in modules.items():
        module_name, path = data
        try:
            if module_name:
                importlib.import_module(module_name)
            report[key] = {"available": path.exists()}
        except Exception as exc:
            report[key] = {"available": path.exists(), "error": str(exc)}
    report["env_loader"] = {
        "available": True,
        "loaded_files": env_report["loaded_files"],
        "loaded_key_count": len(env_report["loaded_keys"]),
        "selected_provider": env_report["provider_report"]["selected_provider"],
        "provider_sequence": env_report["provider_report"]["provider_sequence"],
        "llm_timeout_seconds": env_report["timeout_report"]["llm_timeout_seconds"],
        "llm_max_retries": env_report["timeout_report"]["llm_max_retries"],
        "llm_retry_backoff_seconds": env_report["timeout_report"]["llm_retry_backoff_seconds"],
    }
    return report


def _aggregate_nested_status(results: list[dict[str, Any]]) -> str:
    for result in results:
        if _nested_result_status(result) != "ok":
            return "degraded"
    return "ok"


def _nested_result_status(result: dict[str, Any]) -> str:
    if not isinstance(result, dict):
        return "failed"
    status = result.get("status")
    if isinstance(status, str) and status:
        return status
    run = result.get("run")
    if isinstance(run, dict):
        nested_status = run.get("status")
        if isinstance(nested_status, str) and nested_status:
            return nested_status
    return "ok"


def _summarize_nested_failures(kind: str, results: list[dict[str, Any]]) -> str:
    failures: list[str] = []
    for result in results:
        status = _nested_result_status(result)
        if status == "ok":
            continue
        run = result.get("run") if isinstance(result, dict) else None
        request_id = None
        if isinstance(run, dict):
            request_id = run.get("request_id")
        if not request_id and isinstance(result, dict):
            request_id = result.get("request_id")
        failures.append(f"{request_id or 'unknown'}:{status}")
    if not failures:
        return f"{kind}_nested_failure"
    return f"{kind}_nested_failure: {', '.join(failures)}"


def _fallback_insight(item: NormalizedItem) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "degraded",
        "run": {"request_id": item.id, "status": "degraded", "mode": "fallback-insight"},
        "insights": [
            {
                "id": f"{item.id}-insight",
                "statement": item.summary or item.title,
                "confidence": 0.55,
                "evidence_refs": item.evidence,
            }
        ],
        "open_questions": [
            {
                "id": f"{item.id}-oq",
                "statement": "What is the smallest follow-up experiment worth running?",
                "confidence": 0.4,
                "evidence_refs": item.evidence,
            }
        ],
    }


def _fallback_gate(item: NormalizedItem, dependency_health: dict[str, str]) -> dict[str, Any]:
    score = 72 if item.kind == "paper" else 68
    verdict = "go" if score >= 70 else "hold"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "degraded",
        "run": {"request_id": item.id, "status": "degraded", "mode": "fallback-gate"},
        "decision": {"verdict": verdict, "total_score": score, "confidence": 0.51},
        "next_step": {
            "recommended_action": "run_minimal_probe" if verdict == "go" else "gather_evidence",
            "minimal_probe": f"Review {item.url} and define one concrete follow-up.",
        },
        "reasoning_summary": item.summary or item.title,
        "dependency_health": dependency_health,
    }


def _load_log(path: Path, key: str) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, key: []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload.setdefault(key, [])
    for entry in payload.get(key, []):
        if isinstance(entry, dict):
            entry.setdefault("schema_version", SCHEMA_VERSION)
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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
