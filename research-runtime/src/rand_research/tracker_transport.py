from __future__ import annotations

import json
import urllib.parse
from pathlib import Path
from typing import Any

from rand_research.artifact_schema import validate_artifact_payload
from rand_research.env_loader import ensure_repo_paths
from rand_research.http_utils import INTEGRATION_MAX_BYTES, request_bytes


class _JsonResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class JsonHttpClient:
    """Provider-neutral JSON client used by tracker adapters."""

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> _JsonResponse:
        if params:
            separator = "&" if "?" in url else "?"
            url = url + separator + urllib.parse.urlencode(params)
        return self._request(url, headers=headers, method="GET")

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> _JsonResponse:
        return self._request(url, headers=headers, method="POST", payload=json)

    def _request(
        self,
        url: str,
        *,
        headers: dict[str, str],
        method: str,
        payload: dict[str, Any] | None = None,
    ) -> _JsonResponse:
        response = request_bytes(
            url,
            headers=headers,
            data=(
                json.dumps(payload, ensure_ascii=False).encode("utf-8")
                if payload is not None
                else None
            ),
            method=method,
            timeout_seconds=180,
            max_bytes=INTEGRATION_MAX_BYTES,
            allowed_content_types={"application/json"},
        )
        decoded = json.loads(response.body.decode(response.charset))
        if not isinstance(decoded, dict):
            raise ValueError("tracker response must be a JSON object")
        return _JsonResponse(decoded)


class TrackerBridgeTransport:
    def __init__(
        self,
        *,
        db_path: Path,
        connection_id: str,
        task_id: str,
        http_client: Any | None = None,
    ) -> None:
        self.db_path = db_path
        self.connection_id = connection_id
        self.task_id = task_id
        self.http_client = http_client or JsonHttpClient()

    def __call__(self, handoff: dict[str, Any]) -> dict[str, Any]:
        validation = validate_artifact_payload(handoff, "downstream_handoff")
        if validation["status"] != "ok" or validation.get("legacy"):
            raise ValueError("live delivery requires a valid artifact schema 2.0 handoff")

        issues = handoff.get("tracker_bridge", {}).get("issues", [])
        if not isinstance(issues, list):
            raise ValueError("tracker_bridge.issues must be an array")

        service, connection = self._build_service()
        results: list[dict[str, Any]] = []
        try:
            for issue in issues:
                try:
                    event = service.create_outbound_issue(
                        connection_id=self.connection_id,
                        task_id=self.task_id,
                        handoff_id=str(handoff["handoff_id"]),
                        handoff_item_id=str(issue["handoff_item_id"]),
                        title=str(issue["title"]),
                        body=str(issue["body"]),
                        labels=[str(label) for label in issue.get("labels", [])],
                    )
                    results.append(
                        {
                            "handoff_item_id": issue["handoff_item_id"],
                            "status": event.status,
                            "remote_ref": event.remote_ref,
                            "sync_event_ref": f"tracker:sync_event:local:{event.id}",
                            "error": event.error_message,
                        }
                    )
                except Exception as exc:
                    results.append(
                        {
                            "handoff_item_id": issue.get("handoff_item_id"),
                            "status": "failed",
                            "remote_ref": None,
                            "sync_event_ref": None,
                            "error": f"{type(exc).__name__}: tracker delivery failed",
                        }
                    )
        finally:
            connection.close()

        applied = sum(item["status"] == "applied" for item in results)
        skipped = sum(item["status"] == "skipped" for item in results)
        failed = sum(item["status"] not in {"applied", "skipped"} for item in results)
        attempted = len(results)
        if failed == 0:
            verdict = "ok"
        elif applied + skipped:
            verdict = "degraded"
        else:
            verdict = "failed"
        return {
            "sent": applied > 0,
            "success": failed == 0,
            "destination_verdict": verdict,
            "accepted_by": "tracker-bridge",
            "attempted": attempted,
            "applied": applied,
            "skipped": skipped,
            "failed": failed,
            "remote_refs": [
                item["remote_ref"] for item in results if item.get("remote_ref")
            ],
            "sync_event_refs": [
                item["sync_event_ref"] for item in results if item.get("sync_event_ref")
            ],
            "results": results,
            "error": None if failed == 0 else f"{failed} tracker issue delivery item(s) failed",
        }

    def _build_service(self) -> tuple[Any, Any]:
        ensure_repo_paths()
        from tracker_bridge.adapters.github import GitHubAdapter  # type: ignore[import-not-found]
        from tracker_bridge.db import connect  # type: ignore[import-not-found]
        from tracker_bridge.repositories.connection import TrackerConnectionRepository  # type: ignore[import-not-found]
        from tracker_bridge.repositories.entity_link import EntityLinkRepository  # type: ignore[import-not-found]
        from tracker_bridge.repositories.issue_cache import IssueCacheRepository  # type: ignore[import-not-found]
        from tracker_bridge.repositories.sync_event import SyncEventRepository  # type: ignore[import-not-found]
        from tracker_bridge.services.tracker_integration_service import (  # type: ignore[import-not-found]
            TrackerIntegrationService,
        )

        connection = connect(self.db_path)
        service = TrackerIntegrationService(
            connection_repo=TrackerConnectionRepository(connection),
            issue_repo=IssueCacheRepository(connection),
            link_repo=EntityLinkRepository(connection),
            sync_repo=SyncEventRepository(connection),
        )
        service.register_adapter("github", GitHubAdapter(http_client=self.http_client))
        return service, connection