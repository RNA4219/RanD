from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass

SOURCE_MAX_BYTES = 5 * 1024 * 1024
INTEGRATION_MAX_BYTES = 10 * 1024 * 1024
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class HttpResponse:
    body: bytes
    content_type: str
    charset: str
    final_url: str


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urljoin(req.full_url, newurl)
        validate_http_url(target)
        original = urllib.parse.urlsplit(req.full_url)
        redirected = urllib.parse.urlsplit(target)
        if (
            _authority(original) != _authority(redirected)
            and os.environ.get("RAND_ALLOW_CROSS_HOST_REDIRECT") != "1"
        ):
            raise RuntimeError("cross-host redirect is not allowed")
        return super().redirect_request(req, fp, code, msg, headers, target)


def validate_http_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme == "https":
        return
    if parsed.scheme == "http":
        if parsed.hostname in _LOCAL_HOSTS:
            return
        if os.environ.get("RAND_ALLOW_INSECURE_HTTP") == "1":
            return
        raise ValueError("non-local HTTP requires RAND_ALLOW_INSECURE_HTTP=1")
    raise ValueError(f"unsupported URL scheme: {parsed.scheme or 'missing'}")


def request_bytes(
    url: str,
    *,
    headers: dict[str, str],
    timeout_seconds: int,
    max_bytes: int,
    allowed_content_types: Iterable[str],
    data: bytes | None = None,
    method: str | None = None,
) -> HttpResponse:
    validate_http_url(url)
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )
    opener = urllib.request.build_opener(_SafeRedirectHandler())
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            final_url = response.geturl()
            validate_http_url(final_url)
            content_type = response.headers.get_content_type().lower()
            allowed = {value.lower() for value in allowed_content_types}
            if content_type not in allowed:
                raise ValueError(f"unexpected Content-Type: {content_type}")
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise ValueError(f"response exceeds {max_bytes} bytes")
            charset = response.headers.get_content_charset() or "utf-8"
            return HttpResponse(body, content_type, charset, final_url)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}") from exc


def _authority(parsed: urllib.parse.SplitResult) -> tuple[str | None, int | None]:
    return parsed.hostname, parsed.port