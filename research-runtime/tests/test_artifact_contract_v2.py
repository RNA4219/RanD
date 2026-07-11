from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from rand_research.artifact_schema import (
    ARTIFACT_SCHEMA_VERSION,
    build_artifact_envelope,
    validate_artifact_payload,
)
from rand_research.models import SCHEMA_VERSION


def _valid_report() -> dict:
    return build_artifact_envelope(
        {
            "status": "ok",
            "status_reason": [],
            "state_context": {},
            "artifacts": {},
            "dependency_health": {},
        },
        artifact_id="rand:artifact:run-1:report",
        artifact_type="report",
        created_at="2026-07-11T09:00:00+09:00",
        input_refs=["rand:run:run-1"],
        source_refs=["https://example.test/source"],
        downstream_allowed_uses=["review"],
    )


def test_schema_2_envelope_is_valid() -> None:
    payload = _valid_report()
    result = validate_artifact_payload(payload, "report")
    assert payload["schema_version"] == ARTIFACT_SCHEMA_VERSION
    assert result["status"] == "ok"
    assert result["legacy"] is False


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "type",
        "producer",
        "created_at",
        "input_refs",
        "source_refs",
        "status",
        "assumptions",
        "limitations",
        "review_required",
        "downstream_allowed_uses",
    ],
)
def test_schema_2_rejects_missing_contract_field(field: str) -> None:
    payload = _valid_report()
    del payload[field]
    result = validate_artifact_payload(payload, "report")
    assert result["status"] == "failed"
    assert field in " ".join(issue["message"] for issue in result["issues"])


def test_schema_2_rejects_created_at_without_timezone() -> None:
    payload = _valid_report()
    payload["created_at"] = "2026-07-11T09:00:00"
    result = validate_artifact_payload(payload, "report")
    assert result["status"] == "failed"
    assert "date-time" in " ".join(issue["message"] for issue in result["issues"])


def test_schema_1_is_legacy_warning_compatible() -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "status_reason": [],
        "state_context": {},
        "artifacts": {},
        "dependency_health": {},
    }
    result = validate_artifact_payload(payload, "report")
    assert result["status"] == "ok"
    assert result["legacy"] is True
    assert result["warnings"]


@pytest.mark.parametrize(
    ("kind", "expected"),
    [("v2", 0), ("legacy", 2), ("invalid", 1)],
)
def test_validate_artifact_cli_exit_codes(tmp_path: Path, kind: str, expected: int) -> None:
    if kind == "v2":
        payload = _valid_report()
    elif kind == "legacy":
        payload = {
            "schema_version": SCHEMA_VERSION,
            "status": "ok",
            "status_reason": [],
            "state_context": {},
            "artifacts": {},
            "dependency_health": {},
        }
    else:
        payload = {"schema_version": ARTIFACT_SCHEMA_VERSION, "type": "report"}

    path = tmp_path / "report.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "rand_research.cli",
            "validate-artifact",
            "--path",
            str(path),
            "--type",
            "report",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == expected, result.stderr
    output = json.loads(result.stdout)
    assert output["status"] == ("failed" if kind == "invalid" else "ok")