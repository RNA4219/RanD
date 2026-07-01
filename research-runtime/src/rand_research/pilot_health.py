from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rand_research.artifact_schema import validate_artifact_path
from rand_research.config import load_heartbeat_config
from rand_research.metrics import collect_metrics
from rand_research.models import SCHEMA_VERSION


def evaluate_pilot_readiness(runtime_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    latest_run = _latest_run_dir(runtime_root / "runs")
    metrics = collect_metrics(runtime_root)

    if latest_run is None:
        checks.append(_check("latest_run", "fail", "no run artifact directory found"))
    else:
        checks.extend(_validate_latest_run(latest_run))

    checks.append(_validate_operations_state(runtime_root / "state" / "operations-state.json"))
    checks.append(_validate_heartbeat_config())
    checks.extend(_evaluate_metrics(metrics))

    status = _rollup_status(checks)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "summary": _summary_for(status),
        "latest_run_id": latest_run.name if latest_run else None,
        "checks": checks,
        "metrics": metrics,
    }


def _latest_run_dir(runs_root: Path) -> Path | None:
    if not runs_root.exists():
        return None
    candidates = [path for path in runs_root.iterdir() if path.is_dir() and (path / "report.json").exists()]
    return max(candidates, key=lambda path: path.name) if candidates else None


def _validate_latest_run(run_dir: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    report_path = run_dir / "report.json"
    report_validation = _validate_path_check("latest_report_schema", report_path, "report")
    checks.append(report_validation)

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        checks.append(_check("latest_report_status", "fail", f"report.json is unreadable: {exc}"))
        return checks

    report_status = report.get("status", "unknown")
    if report_status == "failed":
        level = "fail"
    elif report_status == "degraded":
        level = "warn"
    else:
        level = "ok"
    checks.append(
        _check(
            "latest_report_status",
            level,
            f"latest report status is {report_status}",
            {"run_id": report.get("run_meta", {}).get("run_id")},
        )
    )

    downstream_path = run_dir / "downstream_handoff.json"
    if downstream_path.exists():
        checks.append(_validate_path_check("downstream_handoff_schema", downstream_path, "downstream_handoff"))
    else:
        checks.append(_check("downstream_handoff_schema", "warn", "latest run has no downstream_handoff.json"))
    return checks


def _validate_operations_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _check("operations_state_schema", "warn", "operations-state.json does not exist yet")
    return _validate_path_check("operations_state_schema", path, "operations_state")


def _validate_heartbeat_config() -> dict[str, Any]:
    try:
        config = load_heartbeat_config()
    except Exception as exc:
        return _check("heartbeat_config", "fail", f"heartbeat config is unreadable: {exc}")
    if not config.get("default_preset"):
        return _check("heartbeat_config", "fail", "default_preset is missing")
    if not config.get("rules"):
        return _check("heartbeat_config", "warn", "heartbeat rules are empty")
    return _check(
        "heartbeat_config",
        "ok",
        "heartbeat config is loadable",
        {"timezone": config.get("timezone", "Asia/Tokyo"), "default_preset": config.get("default_preset")},
    )


def _evaluate_metrics(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if metrics.get("run_count", 0) <= 0:
        checks.append(_check("run_history", "fail", "no successful report history is available"))
    else:
        checks.append(_check("run_history", "ok", "run history is available", {"run_count": metrics.get("run_count")}))

    pending_count = int(metrics.get("pending_notification_count", 0))
    failed_count = int(metrics.get("notification_failure_count", 0))
    if failed_count:
        checks.append(_check("notification_outbox", "warn", "failed notifications need review", {"failed_count": failed_count}))
    elif pending_count:
        checks.append(_check("notification_outbox", "warn", "pending notifications are queued", {"pending_count": pending_count}))
    else:
        checks.append(_check("notification_outbox", "ok", "notification outbox has no pending or failed entries"))

    tracker_failures = int(metrics.get("tracker_sync_failure_count", 0))
    checks.append(
        _check(
            "tracker_sync",
            "warn" if tracker_failures else "ok",
            "tracker sync has failures" if tracker_failures else "tracker sync has no recorded failures",
            {"failure_count": tracker_failures},
        )
    )
    return checks


def _validate_path_check(name: str, path: Path, artifact_type: str) -> dict[str, Any]:
    try:
        validation = validate_artifact_path(path, artifact_type)
    except Exception as exc:
        return _check(name, "fail", f"{path.name} validation failed: {exc}", {"path": str(path)})
    return _check(
        name,
        "ok" if validation.get("status") == "ok" else "fail",
        f"{path.name} schema {validation.get('status')}",
        {"path": str(path), "issues": validation.get("issues", [])},
    )


def _rollup_status(checks: list[dict[str, Any]]) -> str:
    levels = {check["level"] for check in checks}
    if "fail" in levels:
        return "no_go"
    if "warn" in levels:
        return "degraded"
    return "go"


def _summary_for(status: str) -> str:
    if status == "go":
        return "pilot runtime checks passed"
    if status == "degraded":
        return "pilot runtime can run, but queued or degraded items need review"
    return "pilot runtime is not ready"


def _check(name: str, level: str, message: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "level": level, "message": message, "detail": detail or {}}
