from __future__ import annotations

import csv
import json
import re
from io import StringIO
from pathlib import Path
from typing import Any

from rand_research.io_utils import atomic_write_text
from rand_research.models import SCHEMA_VERSION


def build_shadow_eval_template(run_dir: Path) -> dict[str, Any]:
    kano_path = run_dir / "kano.json"
    if not kano_path.exists():
        raise FileNotFoundError(f"kano.json not found: {kano_path}")
    kano = json.loads(kano_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for candidate in kano.get("kano_candidates", []):
        for evidence in candidate.get("evidence", []):
            rows.append(
                {
                    "candidate_id": candidate.get("candidate_id"),
                    "candidate_statement": candidate.get("statement"),
                    "kano_type": candidate.get("kano_type"),
                    "evidence_id": evidence.get("evidence_id"),
                    "source_ref": evidence.get("source_ref"),
                    "source_type": evidence.get("source_type"),
                    "source_tier": evidence.get("source_tier"),
                    "locale": evidence.get("locale"),
                    "summary": evidence.get("summary"),
                    "relevance_score_1_5": "",
                    "evidence_quality_1_5": "",
                    "bias_flags": "",
                    "promote_decision": "pending",
                    "reviewer_note": "",
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "template_type": "kano_shadow_eval",
        "run_id": kano.get("request_id", "").replace("kano-", ""),
        "topic": kano.get("topic"),
        "review_fields": [
            "relevance_score_1_5",
            "evidence_quality_1_5",
            "bias_flags",
            "promote_decision",
            "reviewer_note",
        ],
        "rows": rows,
    }


def render_shadow_eval_csv(template: dict[str, Any]) -> str:
    rows = template.get("rows", [])
    fieldnames = [
        "candidate_id",
        "candidate_statement",
        "kano_type",
        "evidence_id",
        "source_ref",
        "source_type",
        "source_tier",
        "locale",
        "summary",
        "relevance_score_1_5",
        "evidence_quality_1_5",
        "bias_flags",
        "promote_decision",
        "reviewer_note",
    ]
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return output.getvalue()


def build_tracker_review(source_path: Path) -> dict[str, Any]:
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    issues = _extract_dry_run_issues(payload)
    return {
        "schema_version": SCHEMA_VERSION,
        "review_type": "tracker_dry_run_issue_review",
        "source_path": str(source_path),
        "issue_count": len(issues),
        "issues": [
            {
                "review_id": f"TR-{index:03d}",
                "title": issue.get("title"),
                "body": issue.get("body", ""),
                "labels": issue.get("labels", []),
                "source_item_id": issue.get("source_item_id"),
                "review_decision": "pending",
                "reviewer_note": "",
                "ready_to_send": False,
            }
            for index, issue in enumerate(issues, start=1)
        ],
    }


def generate_task_seed_drafts(handoff_path: Path, out_dir: Path, dry_run: bool = True) -> dict[str, Any]:
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    items = handoff.get("workflow_cookbook", {}).get("items", [])
    drafts = []
    for index, item in enumerate(items, start=1):
        task_id = f"TASK-GENERATED-{index:03d}"
        filename = f"{task_id}-{_slugify(item.get('title') or 'rand-task')}.md"
        content = _render_task_seed(task_id, item, handoff_path)
        path = out_dir / filename
        drafts.append(
            {
                "task_id": task_id,
                "path": str(path),
                "title": item.get("title"),
                "priority": item.get("priority", "P3"),
                "content": content if dry_run else None,
            }
        )
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(path, content)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "dry_run" if dry_run else "written",
        "source_path": str(handoff_path),
        "out_dir": str(out_dir),
        "draft_count": len(drafts),
        "drafts": drafts,
    }


def write_payload_or_print(payload: dict[str, Any], out_path: Path | None, fmt: str = "json") -> str:
    if fmt == "csv":
        content = render_shadow_eval_csv(payload)
    else:
        content = json.dumps(payload, ensure_ascii=False, indent=2)
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(out_path, content)
    return content


def _extract_dry_run_issues(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if "tracker_bridge" in payload:
        return payload.get("tracker_bridge", {}).get("issues", [])
    if "events" in payload:
        issues: list[dict[str, Any]] = []
        for event in payload.get("events", []):
            issues.extend(event.get("dry_run_issues", []))
        return issues
    if "dry_run_issues" in payload:
        return payload.get("dry_run_issues", [])
    return []


def _render_task_seed(task_id: str, item: dict[str, Any], handoff_path: Path) -> str:
    acceptance = "\n".join(f"- {entry}" for entry in item.get("acceptance", [])) or "- TBD"
    risks = "\n".join(f"- {entry}" for entry in item.get("risks", [])) or "- TBD"
    evidence = "\n".join(f"- {entry}" for entry in item.get("evidence_refs", [])) or "- TBD"
    return "\n".join(
        [
            "---",
            f"task_id: {task_id}",
            "status: draft",
            f"priority: {item.get('priority', 'P3')}",
            f"source: {handoff_path}",
            "---",
            "",
            f"# {item.get('title') or task_id}",
            "",
            "## Objective",
            "",
            item.get("objective", "TBD"),
            "",
            "## Acceptance",
            "",
            acceptance,
            "",
            "## Evidence",
            "",
            evidence,
            "",
            "## Risks",
            "",
            risks,
            "",
        ]
    )


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug[:60] or "rand-task"
