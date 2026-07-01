from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from rand_research.io_utils import atomic_write_text
from rand_research.models import NormalizedItem, SCHEMA_VERSION


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
        "dry_run_issues": _build_dry_run_issues(items, gate_payload),
        "status": "ok",
        "error": None,
    }
    payload["events"].append(event)
    _write_json(path, payload)
    return event


def _build_dry_run_issues(items: list[NormalizedItem], gate_payload: dict[str, Any]) -> list[dict[str, Any]]:
    verdict_by_id = {
        result.get("run", {}).get("request_id"): result.get("decision", {}).get("verdict")
        for result in gate_payload.get("results", [])
    }
    issues: list[dict[str, Any]] = []
    for item in items[:5]:
        verdict = verdict_by_id.get(item.id, "unreviewed")
        issues.append(
            {
                "title": f"[RanD] {item.title}",
                "body": "\n".join(
                    [
                        f"Source: {item.url}",
                        f"Kind: {item.kind}",
                        f"Priority: {item.priority}",
                        f"Gate verdict: {verdict}",
                        "",
                        item.summary or item.title,
                    ]
                ).strip(),
                "labels": ["rand", f"preset-source:{item.source_name}", f"gate:{verdict}"],
                "source_item_id": item.id,
                "status": "dry_run",
            }
        )
    return issues


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
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    atomic_write_text(path, content)
