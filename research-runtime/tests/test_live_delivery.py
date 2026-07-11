from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from rand_research.downstream import build_downstream_handoff
from rand_research.pipeline import _final_status, _prepare_delivery
from rand_research.tracker_transport import TrackerBridgeTransport


def _payloads(count: int = 2) -> dict:
    return {
        "requirements_packet": {
            "packet_id": "rand:packet:run-1",
            "source_refs": ["https://example.test/source"],
            "requirements": [
                {
                    "requirement_id": f"rand:REQ-{index}",
                    "title": f"Requirement {index}",
                    "statement": f"Implement {index}",
                }
                for index in range(count)
            ],
        }
    }


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeService:
    def __init__(self, statuses: list[str]) -> None:
        self.statuses = iter(statuses)
        self.calls: list[dict] = []

    def create_outbound_issue(self, **kwargs):
        self.calls.append(kwargs)
        status = next(self.statuses)
        if status == "raise":
            raise ValueError("connection missing")
        number = len(self.calls)
        return SimpleNamespace(
            id=f"event-{number}",
            status=status,
            remote_ref=f"tracker:issue:github:owner/repo#{number}",
            error_message=None,
        )


def test_live_transport_aggregates_applied_skipped_and_typed_refs(tmp_path) -> None:
    service = FakeService(["applied", "skipped"])
    connection = FakeConnection()
    transport = TrackerBridgeTransport(
        db_path=tmp_path / "tracker.db",
        connection_id="github-main",
        task_id="task-run-1",
    )
    with patch.object(transport, "_build_service", return_value=(service, connection)):
        handoff = build_downstream_handoff(_payloads(), "run-1", mode="live", transport=transport)

    assert handoff is not None
    delivery = handoff["delivery"]
    assert delivery["destination_verdict"] == "ok"
    assert delivery["attempted"] == 2
    assert delivery["applied"] == 1
    assert delivery["skipped"] == 1
    assert delivery["failed"] == 0
    assert all(ref.startswith("tracker:issue:github:") for ref in delivery["remote_refs"])
    assert all(ref.startswith("tracker:sync_event:local:") for ref in delivery["sync_event_refs"])
    assert all(call["task_id"] == "task-run-1" for call in service.calls)
    assert connection.closed is True


def test_replay_reuses_handoff_item_id(tmp_path) -> None:
    service = FakeService(["applied", "skipped"])
    transport = TrackerBridgeTransport(
        db_path=tmp_path / "tracker.db",
        connection_id="github-main",
        task_id="task-run-1",
    )
    with patch.object(
        transport,
        "_build_service",
        side_effect=[(service, FakeConnection()), (service, FakeConnection())],
    ):
        first = build_downstream_handoff(_payloads(1), "run-1", mode="live", transport=transport)
        replay = build_downstream_handoff(_payloads(1), "run-1", mode="live", transport=transport)

    assert first is not None and replay is not None
    assert service.calls[0]["handoff_item_id"] == service.calls[1]["handoff_item_id"]
    assert first["delivery"]["applied"] == 1
    assert replay["delivery"]["skipped"] == 1

def test_live_transport_partial_and_total_failure_rollup(tmp_path) -> None:
    for statuses, expected in ((["applied", "raise"], "degraded"), (["raise", "raise"], "failed")):
        service = FakeService(statuses)
        transport = TrackerBridgeTransport(
            db_path=tmp_path / "tracker.db",
            connection_id="github-main",
            task_id="task-run-1",
        )
        with patch.object(transport, "_build_service", return_value=(service, FakeConnection())):
            handoff = build_downstream_handoff(_payloads(), "run-1", mode="live", transport=transport)
        assert handoff is not None
        assert handoff["delivery"]["destination_verdict"] == expected


def test_dry_run_and_shadow_never_call_transport() -> None:
    transport = Mock(side_effect=AssertionError("transport must not be called"))
    for mode in ("dry_run", "shadow"):
        handoff = build_downstream_handoff(_payloads(1), "run-1", mode=mode, transport=transport)
        assert handoff is not None
        assert handoff["delivery"]["attempted"] is False
    transport.assert_not_called()


def test_live_delivery_requires_mode_and_explicit_confirmation(monkeypatch) -> None:
    runtime = {
        "downstream_handoff_mode": "dry_run",
        "tracker_bridge_db_path": "state/tracker.db",
        "tracker_connection_id": "github-main",
    }
    preset = {"downstream_handoff_mode": "shadow"}

    monkeypatch.delenv("RAND_CONFIRM_LIVE_DELIVERY", raising=False)
    mode, transport, error, confirmed = _prepare_delivery(runtime, preset, "live", False, "run-1")
    assert (mode, transport is None, confirmed) == ("live", True, False)
    assert "--confirm-live" in str(error)

    with patch("rand_research.pipeline.TrackerBridgeTransport") as transport_type:
        mode, transport, error, confirmed = _prepare_delivery(runtime, preset, "live", True, "run-1")
    assert mode == "live"
    assert transport is transport_type.return_value
    assert error is None
    assert confirmed is True

    monkeypatch.setenv("RAND_CONFIRM_LIVE_DELIVERY", "1")
    with patch("rand_research.pipeline.TrackerBridgeTransport") as transport_type:
        mode, transport, error, confirmed = _prepare_delivery(runtime, preset, "live", False, "run-1")
    assert transport is transport_type.return_value
    assert confirmed is True

    mode, transport, error, _ = _prepare_delivery(runtime, preset, "dry_run", True, "run-1")
    assert (mode, transport, error) == ("dry_run", None, None)


def test_delivery_failure_controls_run_status() -> None:
    assert _final_status({"sources": "ok", "state": "ok", "report": "ok", "delivery": "failed"}, []) == "failed"
    assert _final_status({"sources": "ok", "state": "ok", "report": "ok", "delivery": "degraded"}, []) == "degraded"


def test_live_transport_rejects_legacy_handoff(tmp_path) -> None:
    transport = TrackerBridgeTransport(
        db_path=tmp_path / "tracker.db",
        connection_id="github-main",
        task_id="task-run-1",
    )
    with pytest.raises(ValueError, match="schema 2.0"):
        transport(
            {
                "schema_version": "1.0",
                "handoff_id": "rand:downstream-run-1",
                "mode": "requirements_packet",
                "workflow_cookbook": {},
                "manual_bb_test_harness": {},
                "code_to_gate": {},
                "tracker_bridge": {"issues": []},
                "status": "live",
                "delivery": {"mode": "live"},
                "error": None,
            }
        )