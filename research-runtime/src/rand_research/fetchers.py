from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from rand_research.http_utils import SOURCE_MAX_BYTES, request_bytes
from rand_research.models import NormalizedItem
from rand_research.paths import workspace_root


def fetch_text(url: str, user_agent: str, timeout_seconds: int) -> str:
    response = request_bytes(
        url,
        headers={"User-Agent": user_agent},
        timeout_seconds=timeout_seconds,
        max_bytes=SOURCE_MAX_BYTES,
        allowed_content_types={
            "text/html",
            "text/plain",
            "application/rss+xml",
            "application/atom+xml",
            "application/xml",
            "text/xml",
        },
    )
    return response.body.decode(response.charset, errors="replace")

class LinkCollector(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self.current_href: str | None = None
        self.current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.current_href = urllib.parse.urljoin(self.base_url, href)
            self.current_text = []

    def handle_data(self, data: str) -> None:
        if self.current_href is not None:
            self.current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self.current_href is None:
            return
        text = html.unescape("".join(self.current_text)).strip()
        if text:
            self.links.append((self.current_href, text))
        self.current_href = None
        self.current_text = []


def collect_source(source: dict[str, Any], user_agent: str, timeout_seconds: int, max_items: int) -> list[NormalizedItem]:
    fetcher = source["fetcher"]
    if fetcher == "arxiv_recent_html":
        html_text = fetch_text(source["url"], user_agent, timeout_seconds)
        return parse_arxiv_recent_html(source, html_text, max_items)
    if fetcher == "generic_html_links":
        html_text = fetch_text(source["url"], user_agent, timeout_seconds)
        return parse_generic_links(source, html_text, max_items)
    if fetcher == "rss_or_html":
        for rss_url in source.get("rss_candidates", []):
            try:
                rss_text = fetch_text(rss_url, user_agent, timeout_seconds)
                local_source = dict(source)
                local_source["rss_used"] = rss_url
                return parse_rss_items(local_source, rss_text, max_items)
            except Exception:
                continue
        html_text = fetch_text(source["url"], user_agent, timeout_seconds)
        return parse_generic_links(source, html_text, max_items)
    if fetcher == "kano_query_seed":
        return build_kano_query_seed_items(source, max_items)
    if fetcher == "kano_shadow_search":
        return collect_kano_shadow_search(source, user_agent, timeout_seconds, max_items)
    if fetcher == "kano_fixture_json":
        fixture_path = workspace_root() / source["fixture_path"]
        return parse_kano_fixture_json(source, fixture_path, max_items)
    if fetcher == "audit_fixture_json":
        fixture_path = workspace_root() / source["fixture_path"]
        return parse_audit_fixture_json(source, fixture_path, max_items)
    raise ValueError(f"Unknown fetcher: {fetcher}")


def parse_arxiv_recent_html(source: dict[str, Any], html_text: str, max_items: int) -> list[NormalizedItem]:
    pattern = re.compile(r"<dt>.*?<a\s+href\s*=\s*\"/abs/(?P<abs>[^\"]+)\".*?</dt>\s*<dd>(?P<body>.*?)</dd>", re.DOTALL)
    title_pattern = re.compile(r"(?:Title:</span>|Title:)\s*(?P<title>.*?)\s*</div>", re.DOTALL)
    abstract_pattern = re.compile(r"<p class=['\"]mathjax['\"]>\s*(?P<summary>.*?)\s*</p>", re.DOTALL)
    author_pattern = re.compile(r"<a href=\"(?:https://arxiv.org)?/search/[^\"]+\">(?P<author>.*?)</a>")
    items: list[NormalizedItem] = []
    for index, match in enumerate(pattern.finditer(html_text)):
        if index >= max_items:
            break
        body = match.group("body")
        title_match = title_pattern.search(body)
        abstract_match = abstract_pattern.search(body)
        authors = [html.unescape(author).strip() for author in author_pattern.findall(body)]
        title = html.unescape(re.sub(r"<.*?>", "", title_match.group("title") if title_match else "")).strip()
        summary = html.unescape(re.sub(r"<.*?>", "", abstract_match.group("summary") if abstract_match else "")).strip()
        if not summary:
            summary = f"Collected from {source['url']}"
        paper_id = match.group("abs").strip()
        items.append(
            NormalizedItem(
                id=f"arxiv-{paper_id}",
                kind="paper",
                source_name=source["name"],
                url=f"https://arxiv.org/abs/{paper_id}",
                title=title or paper_id,
                authors=authors,
                summary=summary,
                claims=_split_claims(summary) or [title],
                evidence=[f"Primary source: {source['url']}"],
                tags=["paper", "arxiv", "cs.AI"],
                priority=max(max_items - index, 1),
                high_priority=index < 3,
                metadata={"seed_url": source["url"], "paper_id": paper_id},
            )
        )
    return items


def parse_generic_links(source: dict[str, Any], html_text: str, max_items: int) -> list[NormalizedItem]:
    parser = LinkCollector(source["url"])
    parser.feed(html_text)
    link_pattern = source.get("link_pattern")
    seen: set[str] = set()
    items: list[NormalizedItem] = []
    for href, text in parser.links:
        if link_pattern and link_pattern not in href:
            continue
        if "#" in href:
            continue
        if href in seen:
            continue
        if text.isdigit() or len(text.strip()) < 4:
            continue
        seen.add(href)
        items.append(
            NormalizedItem(
                id=_slugify(f"{source['name']}-{href}")[:80],
                kind=source["kind"],
                source_name=source["name"],
                url=href,
                title=text,
                summary=f"Collected from {source['url']}",
                claims=[f"{text} was listed on {source['name']}"],
                evidence=[f"Listed link on {source['url']}"],
                tags=[source["kind"], source["name"]],
                priority=max(max_items - len(items), 1),
                high_priority=len(items) < 3,
                metadata={"seed_url": source["url"]},
            )
        )
        if len(items) >= max_items:
            break
    return items


def parse_rss_items(source: dict[str, Any], rss_text: str, max_items: int) -> list[NormalizedItem]:
    root = ET.fromstring(rss_text)
    items: list[NormalizedItem] = []
    for entry in root.findall(".//item")[:max_items]:
        title = (entry.findtext("title") or "").strip()
        link = (entry.findtext("link") or "").strip()
        description = entry.findtext("description") or ""
        summary = html.unescape(re.sub(r"<.*?>", "", description)).strip()
        published = (entry.findtext("pubDate") or "").strip()
        items.append(
            NormalizedItem(
                id=_slugify(f"{source['name']}-{link}")[:80],
                kind=source["kind"],
                source_name=source["name"],
                url=link or source["url"],
                title=title or link,
                published_at=published or None,
                summary=summary,
                claims=_split_claims(summary),
                evidence=[f"RSS source: {source.get('rss_used', source['url'])}"],
                tags=[source["kind"], source["name"]],
                priority=max(max_items - len(items), 1),
                high_priority=len(items) < 3,
                metadata={"seed_url": source["url"]},
            )
        )
    return items


def build_kano_query_seed_items(source: dict[str, Any], max_items: int) -> list[NormalizedItem]:
    topic = source.get("topic", "RanD KanoMode")
    locales = source.get("locales", ["ja-JP", "en-US"])
    query_families = source.get("query_families", [])
    items: list[NormalizedItem] = []
    for family in query_families:
        family_name = family["name"]
        kano_type = family.get("kano_type", "questionable")
        for locale in locales:
            template = family.get("templates", {}).get(locale) or family.get("template") or "{topic} {family}"
            query = template.format(topic=topic, family=family_name)
            item_id = _slugify(f"{source['name']}-{family_name}-{locale}")[:80]
            items.append(
                NormalizedItem(
                    id=item_id,
                    kind="kano_evidence",
                    source_name=source["name"],
                    url=f"query://{urllib.parse.quote(query)}",
                    title=f"{topic}: {family_name} evidence search ({locale})",
                    summary=f"Offline query seed for {family_name}: {query}",
                    claims=[f"Search family {family_name} can collect Kano evidence for {topic}"],
                    evidence=[f"Query seed: {query}"],
                    tags=["kano", "query_seed", family_name, locale],
                    priority=max(max_items - len(items), 1),
                    high_priority=len(items) < 3,
                    metadata={
                        "source_type": family_name,
                        "source_tier": family.get("source_tier", "query_seed"),
                        "locale": locale,
                        "kano_type": kano_type,
                        "kano_candidate_id": family.get("candidate_id", family_name),
                        "requirement_statement": family.get("requirement_statement", f"Collect {family_name} evidence for {topic}"),
                        "confidence": family.get("confidence", 0.6),
                        "bias_note": family.get("bias_note", "Query seed requires evidence validation before promotion."),
                        "kill_condition": family.get("kill_condition", "No supporting evidence is found in offline or live review."),
                        "freshness_days": None,
                    },
                )
            )
            if len(items) >= max_items:
                return items
    return items


def collect_kano_shadow_search(
    source: dict[str, Any],
    user_agent: str,
    timeout_seconds: int,
    max_items: int,
) -> list[NormalizedItem]:
    """Collect optional live/search shadow evidence without making CI depend on it.

    The adapter is disabled unless the configured env flag is truthy. When enabled,
    it fetches explicitly configured search pages and turns matching links into
    Kano evidence candidates. This keeps live search as a pilot path while fixture
    eval remains the acceptance source of truth.
    """
    import os

    enabled_env = source.get("enabled_env", "RAND_KANO_SHADOW_SEARCH")
    if str(os.environ.get(enabled_env, "")).lower() not in {"1", "true", "yes", "on"}:
        return []

    urls = source.get("urls", [])
    if not urls:
        urls = _shadow_search_urls_from_families(source)

    items: list[NormalizedItem] = []
    for url_config in urls:
        if len(items) >= max_items:
            break
        if isinstance(url_config, str):
            url = url_config
            metadata: dict[str, Any] = {}
        else:
            url = url_config["url"]
            metadata = dict(url_config.get("metadata", {}))

        html_text = fetch_text(url, user_agent, timeout_seconds)
        local_source = {
            "name": source["name"],
            "kind": "kano_evidence",
            "url": url,
            "link_pattern": source.get("link_pattern"),
        }
        for item in parse_generic_links(local_source, html_text, max_items - len(items)):
            family = metadata.get("source_type", source.get("source_type", "shadow_search"))
            candidate_id = metadata.get("kano_candidate_id") or _slugify(f"{family}-{item.title}")[:48]
            item.kind = "kano_evidence"
            item.source_name = source["name"]
            item.tags = ["kano", "shadow_search", family, metadata.get("locale", "und")]
            item.metadata.update(
                {
                    "source_type": family,
                    "source_tier": metadata.get("source_tier", "user_signal"),
                    "locale": metadata.get("locale", "und"),
                    "kano_type": metadata.get("kano_type", "questionable"),
                    "kano_candidate_id": candidate_id,
                    "requirement_statement": metadata.get("requirement_statement", item.title),
                    "confidence": metadata.get("confidence", 0.55),
                    "bias_note": metadata.get("bias_note", "Live shadow search evidence may include ranking and SEO bias."),
                    "kill_condition": metadata.get("kill_condition", "Human review rejects the live evidence as irrelevant or stale."),
                    "freshness_days": metadata.get("freshness_days"),
                    "shadow_search_url": url,
                }
            )
            item.evidence.append(f"Shadow search source: {url}")
            items.append(item)
            if len(items) >= max_items:
                break
    return items


def _shadow_search_urls_from_families(source: dict[str, Any]) -> list[dict[str, Any]]:
    endpoint_template = source.get("search_endpoint_template")
    if not endpoint_template:
        return []
    topic = source.get("topic", "RanD KanoMode")
    locales = source.get("locales", ["ja-JP", "en-US"])
    urls: list[dict[str, Any]] = []
    for family in source.get("query_families", []):
        for locale in locales:
            template = family.get("templates", {}).get(locale) or family.get("template") or "{topic} {family}"
            query = template.format(topic=topic, family=family.get("name", "kano"))
            urls.append(
                {
                    "url": endpoint_template.format(query=urllib.parse.quote_plus(query), locale=locale),
                    "metadata": {
                        "source_type": family.get("name", "shadow_search"),
                        "source_tier": family.get("source_tier", "user_signal"),
                        "locale": locale,
                        "kano_type": family.get("kano_type", "questionable"),
                        "kano_candidate_id": family.get("candidate_id"),
                        "requirement_statement": family.get("requirement_statement"),
                        "confidence": family.get("confidence", 0.55),
                        "bias_note": family.get("bias_note"),
                        "kill_condition": family.get("kill_condition"),
                    },
                }
            )
    return urls


def parse_kano_fixture_json(source: dict[str, Any], fixture_path: Path, max_items: int) -> list[NormalizedItem]:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    records = payload.get("items", payload if isinstance(payload, list) else [])
    items: list[NormalizedItem] = []
    for record in records[:max_items]:
        metadata = dict(record.get("metadata", {}))
        metadata.setdefault("source_type", record.get("source_type", "fixture"))
        metadata.setdefault("source_tier", record.get("source_tier", "user_signal"))
        metadata.setdefault("locale", record.get("locale", "ja-JP"))
        metadata.setdefault("freshness_days", record.get("freshness_days"))
        item_id = record.get("id") or _slugify(f"{source['name']}-{record.get('title', len(items))}")[:80]
        items.append(
            NormalizedItem(
                id=item_id,
                kind=record.get("kind", "kano_evidence"),
                source_name=source["name"],
                url=record.get("url", f"fixture://{item_id}"),
                title=record.get("title", item_id),
                published_at=record.get("published_at"),
                summary=record.get("summary", ""),
                claims=record.get("claims", []),
                evidence=record.get("evidence", []),
                tags=record.get("tags", ["kano", "fixture"]),
                priority=record.get("priority", max(max_items - len(items), 1)),
                high_priority=record.get("high_priority", len(items) < 3),
                metadata=metadata,
            )
        )
    return items


def parse_audit_fixture_json(source: dict[str, Any], fixture_path: Path, max_items: int) -> list[NormalizedItem]:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    records = payload.get("items", payload if isinstance(payload, list) else [])
    items: list[NormalizedItem] = []
    for record in records[:max_items]:
        metadata = dict(record.get("metadata", {}))
        metadata.setdefault("source_type", record.get("source_type", "audit"))
        metadata.setdefault("source_tier", record.get("source_tier", "primary"))
        metadata.setdefault("locale", record.get("locale", "ja-JP"))
        metadata.setdefault("freshness_days", record.get("freshness_days"))
        metadata.setdefault("requirement_id", record.get("requirement_id", "REQ-UNKNOWN"))
        metadata.setdefault("original_text", record.get("original_text", record.get("title", "")))
        metadata.setdefault("kano_type", record.get("kano_type", "questionable"))
        metadata.setdefault("testability", record.get("testability", "medium"))
        metadata.setdefault("implementation_alignment", record.get("implementation_alignment", "unknown"))
        metadata.setdefault("risks", record.get("risks", []))
        metadata.setdefault("issues", record.get("issues", []))
        metadata.setdefault("suggested_action", record.get("suggested_action", "確認"))
        item_id = record.get("id") or _slugify(f"{source['name']}-{record.get('title', len(items))}")[:80]
        items.append(
            NormalizedItem(
                id=item_id,
                kind=record.get("kind", "audit_evidence"),
                source_name=source["name"],
                url=record.get("url", f"fixture://{item_id}"),
                title=record.get("title", item_id),
                published_at=record.get("published_at"),
                summary=record.get("summary", ""),
                claims=record.get("claims", []),
                evidence=record.get("evidence", []),
                tags=record.get("tags", ["audit", "fixture"]),
                priority=record.get("priority", max(max_items - len(items), 1)),
                high_priority=record.get("high_priority", len(items) < 3),
                metadata=metadata,
            )
        )
    return items


def _slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()


def _split_claims(summary: str) -> list[str]:
    if summary.startswith("Collected from "):
        return []
    return [part.strip() for part in re.split(r"[。.!?]\s*", summary) if part.strip()][:3]
