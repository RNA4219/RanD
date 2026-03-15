"""Misskey notifier for RanD heartbeat results."""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class MisskeyPost:
    """Represents a Misskey post."""
    text: str
    visibility: str = "home"
    reply_id: str | None = None
    cw: str | None = None


@dataclass
class HeartbeatSummary:
    """Summary of a heartbeat run for posting."""
    preset: str
    collected_count: int
    open_tasks_before: int
    open_tasks_after: int
    timestamp: str
    top_items: list[dict[str, str]]

    @classmethod
    def from_report(cls, report: dict[str, Any], preset: str) -> "HeartbeatSummary":
        """Create summary from research report."""
        items = report.get("collected_items", [])
        state_ctx = report.get("state_context", {})
        before_count = len(state_ctx.get("before", {}).get("open_tasks", []))
        after_count = len(state_ctx.get("after", {}).get("open_tasks", []))

        return cls(
            preset=preset,
            collected_count=len(items),
            open_tasks_before=before_count,
            open_tasks_after=after_count,
            timestamp=datetime.now(timezone.utc).isoformat(),
            top_items=[
                {"title": item.get("title", ""), "url": item.get("url", "")}
                for item in items[:3]
                if item.get("title")
            ],
        )

    def to_misskey_text(self, max_length: int = 3000) -> str:
        """Format summary as Misskey post text."""
        lines = [
            f"[RanD Heartbeat] {self.preset}",
            f"Collected: {self.collected_count} items",
            f"Open tasks: {self.open_tasks_before} -> {self.open_tasks_after}",
        ]

        if self.top_items:
            lines.append("")
            lines.append("Top items:")
            for item in self.top_items:
                title = item.get("title", "")[:50]
                lines.append(f"- {title}")

        text = "\n".join(lines)
        if len(text) > max_length:
            text = text[:max_length - 3] + "..."

        return text


class MisskeyNotifier:
    """Client for posting to Misskey."""

    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token

    def post(self, post: MisskeyPost) -> dict[str, Any]:
        """Create a note on Misskey."""
        url = f"{self.base_url}/api/notes/create"
        payload: dict[str, Any] = {
            "i": self.api_token,
            "text": post.text,
            "visibility": post.visibility,
        }
        if post.reply_id:
            payload["replyId"] = post.reply_id
        if post.cw:
            payload["cw"] = post.cw

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return {"ok": True, "response": json.load(resp)}
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8") if e.fp else ""
            return {"ok": False, "error": str(e), "body": body}
        except Exception as e:
            return {"ok": False, "error": str(e)}


def post_heartbeat_summary(
    report: dict[str, Any],
    preset: str,
    misskey_url: str,
    misskey_token: str,
    visibility: str = "home",
) -> dict[str, Any]:
    """Post a heartbeat summary to Misskey.

    Args:
        report: Research report dict
        preset: Preset name
        misskey_url: Misskey instance URL
        misskey_token: API token
        visibility: Note visibility (home, public, followers, etc.)

    Returns:
        Result dict with ok status and any error details
    """
    summary = HeartbeatSummary.from_report(report, preset)
    notifier = MisskeyNotifier(misskey_url, misskey_token)

    post = MisskeyPost(
        text=summary.to_misskey_text(),
        visibility=visibility,
    )

    return notifier.post(post)