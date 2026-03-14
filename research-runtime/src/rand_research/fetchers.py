from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Any

from rand_research.models import NormalizedItem


def fetch_text(url: str, user_agent: str, timeout_seconds: int) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


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


def _slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()


def _split_claims(summary: str) -> list[str]:
    if summary.startswith("Collected from "):
        return []
    return [part.strip() for part in re.split(r"[。.!?]\s*", summary) if part.strip()][:3]
