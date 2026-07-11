from __future__ import annotations

import importlib
import json
import os
import subprocess
from typing import Any

from rand_research.env_loader import ensure_repo_paths, load_env_from_peer_repos
from rand_research.http_utils import INTEGRATION_MAX_BYTES, request_bytes
from rand_research.models import SCHEMA_VERSION, NormalizedItem
from rand_research.paths import installer_root


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
    api_payloads = [build_insight_payload(item) for item in items]
    api_result, api_error = _run_external_api("insight", api_payloads)
    if api_result is not None:
        return api_result
    if api_error:
        subagent_result = _run_subagent("insight", api_payloads, api_error)
        if subagent_result is not None:
            return subagent_result
    try:
        insight_core = importlib.import_module("insight_core")
        results = []
        for payload in api_payloads:
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
        subagent_result = _run_subagent("insight", api_payloads, str(exc))
        if subagent_result is not None:
            return subagent_result
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
    api_requests = [_build_gate_api_payload(item, dependency_health) for item in targets]
    api_result, api_error = _run_external_api("gate", api_requests, dependency_health)
    if api_result is not None:
        return api_result
    if api_error:
        subagent_result = _run_subagent("gate", api_requests, api_error, dependency_health)
        if subagent_result is not None:
            return subagent_result
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
        subagent_result = _run_subagent("gate", api_requests, str(exc), dependency_health)
        if subagent_result is not None:
            return subagent_result
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "degraded",
            "mode": "fallback",
            "results": [_fallback_gate(item, dependency_health) for item in targets],
            "error": str(exc),
            "dependency_health": dependency_health,
        }


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
    report["external_api"] = {
        "insight_api_configured": bool(os.environ.get("RAND_INSIGHT_API_URL")),
        "gate_api_configured": bool(os.environ.get("RAND_GATE_API_URL")),
        "insight_subagent_configured": bool(os.environ.get("RAND_INSIGHT_SUBAGENT_ARGV")),
        "insight_shell_subagent_configured": bool(os.environ.get("RAND_INSIGHT_SUBAGENT_CMD")),
        "gate_subagent_configured": bool(os.environ.get("RAND_GATE_SUBAGENT_ARGV")),
        "gate_shell_subagent_configured": bool(os.environ.get("RAND_GATE_SUBAGENT_CMD")),
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


def _build_gate_api_payload(item: NormalizedItem, dependency_health: dict[str, str]) -> dict[str, Any]:
    return {
        "request_id": item.id,
        "hypothesis": f"{item.title} should be evaluated as a small PoC candidate.",
        "poc_spec": {
            "objective": f"Verify whether {item.title} has practical follow-up value.",
            "problem": item.summary or item.title,
            "target_user_or_context": "RanD daily research watch",
            "success_metrics": ["Actionable follow-up identified"],
            "failure_or_abort_criteria": ["No meaningful differentiator found"],
            "minimum_scope": "Read the item, summarize it, and define one small next step.",
            "non_goals": ["Production rollout"],
            "required_inputs_or_tools": [item.url],
            "validation_plan": "Collect evidence and compare novelty, feasibility, and impact.",
        },
        "evidence_bundle": {
            "claims": item.claims,
            "sources": [item.url],
            "gaps": ["Full manual review not completed yet"],
        },
        "decision_context": {
            "chain": "research -> insight -> gate -> sync -> notify",
            "dependency_health": dependency_health,
        },
    }


def _run_external_api(
    kind: str,
    requests: list[dict[str, Any]],
    dependency_health: dict[str, str] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    url = os.environ.get(f"RAND_{kind.upper()}_API_URL")
    if not url:
        return None, None
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "requests": requests,
    }
    if dependency_health is not None:
        payload["dependency_health"] = dependency_health
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "RanDResearchRuntime/0.2",
    }
    token = os.environ.get(f"RAND_{kind.upper()}_API_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = _post_json(url, payload, headers, _integration_timeout_seconds())
        results = _coerce_integration_results(response)
        status = response.get("status") or _aggregate_nested_status(results)
        result_payload = {
            "schema_version": SCHEMA_VERSION,
            "status": status,
            "mode": f"{kind}-api",
            "results": results,
            "error": response.get("error") if status != "ok" else None,
        }
        if dependency_health is not None:
            result_payload["dependency_health"] = dependency_health
        return result_payload, None
    except Exception as exc:
        return None, f"{kind}_api_failed: {exc}"


def _run_subagent(
    kind: str,
    requests: list[dict[str, Any]],
    cause: str,
    dependency_health: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    argv_value = os.environ.get(f"RAND_{kind.upper()}_SUBAGENT_ARGV")
    legacy_command = os.environ.get(f"RAND_{kind.upper()}_SUBAGENT_CMD")
    legacy_shell = False
    command: list[str] | str
    if argv_value:
        try:
            parsed = json.loads(argv_value)
        except json.JSONDecodeError as exc:
            return _subagent_failure_payload(
                kind,
                f"{cause}; subagent_argv_invalid_json: {exc}",
                dependency_health,
            )
        if not isinstance(parsed, list) or not parsed or not all(
            isinstance(part, str) and part for part in parsed
        ):
            return _subagent_failure_payload(
                kind,
                f"{cause}; subagent_argv_must_be_nonempty_string_array",
                dependency_health,
            )
        command = parsed
    elif legacy_command and os.environ.get("RAND_ALLOW_SHELL_SUBAGENT") == "1":
        command = legacy_command
        legacy_shell = True
    else:
        return None

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "fallback_cause": cause,
        "requests": requests,
    }
    if dependency_health is not None:
        payload["dependency_health"] = dependency_health
    try:
        completed = subprocess.run(
            command,
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            check=False,
            encoding="utf-8",
            shell=legacy_shell,
            timeout=_integration_timeout_seconds(),
        )
    except Exception as exc:
        return _subagent_failure_payload(kind, f"{cause}; subagent_launch_failed: {exc}", dependency_health)
    if completed.returncode != 0:
        error = (completed.stderr or completed.stdout or "").strip()
        return _subagent_failure_payload(kind, f"{cause}; subagent_failed: {error}", dependency_health)
    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return _subagent_failure_payload(kind, f"{cause}; subagent_invalid_json: {exc}", dependency_health)
    results = _coerce_integration_results(response)
    status = response.get("status") or _aggregate_nested_status(results)
    warnings: list[str] = []
    if legacy_shell:
        warnings.append("legacy shell subagent command enabled by RAND_ALLOW_SHELL_SUBAGENT=1")
        if status == "ok":
            status = "degraded"
    result_payload = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": f"{kind}-subagent",
        "results": results,
        "error": response.get("error") if status != "ok" and not legacy_shell else None,
        "warnings": warnings,
    }
    if dependency_health is not None:
        result_payload["dependency_health"] = dependency_health
    return result_payload

def _subagent_failure_payload(kind: str, error: str, dependency_health: dict[str, str] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "degraded",
        "mode": f"{kind}-subagent",
        "results": [],
        "error": error,
    }
    if dependency_health is not None:
        payload["dependency_health"] = dependency_health
    return payload


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout_seconds: int) -> dict[str, Any]:
    response = request_bytes(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
        timeout_seconds=timeout_seconds,
        max_bytes=INTEGRATION_MAX_BYTES,
        allowed_content_types={"application/json"},
    )
    decoded = json.loads(response.body.decode(response.charset))
    if not isinstance(decoded, dict):
        raise ValueError("integration response must be a JSON object")
    return decoded

def _coerce_integration_results(response: dict[str, Any]) -> list[dict[str, Any]]:
    results = response.get("results", [])
    if isinstance(results, list):
        return [result for result in results if isinstance(result, dict)]
    if isinstance(results, dict):
        return [results]
    return []


def _integration_timeout_seconds() -> int:
    return max(int(os.environ.get("RAND_INTEGRATION_TIMEOUT_SECONDS", "0") or 0), 30)
