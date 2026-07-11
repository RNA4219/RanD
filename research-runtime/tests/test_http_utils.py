from __future__ import annotations

import urllib.request
from email.message import Message
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from rand_research.http_utils import (
    INTEGRATION_MAX_BYTES,
    SOURCE_MAX_BYTES,
    _SafeRedirectHandler,
    request_bytes,
    validate_http_url,
)


class FakeResponse:
    def __init__(self, body: bytes, content_type: str, final_url: str = "https://example.test/data") -> None:
        self._body = body
        self._final_url = final_url
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args) -> None:
        return None

    def geturl(self) -> str:
        return self._final_url

    def read(self, _limit: int) -> bytes:
        return self._body


@pytest.mark.parametrize("url", ["https://example.test", "http://localhost:8000", "http://127.0.0.1"])
def test_https_and_local_http_are_allowed(url: str) -> None:
    validate_http_url(url)


def test_non_local_http_requires_explicit_opt_in() -> None:
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="RAND_ALLOW_INSECURE_HTTP"):
            validate_http_url("http://example.test")
    with patch.dict("os.environ", {"RAND_ALLOW_INSECURE_HTTP": "1"}, clear=True):
        validate_http_url("http://example.test")


def test_cross_host_redirect_is_rejected() -> None:
    handler = _SafeRedirectHandler()
    request = urllib.request.Request("https://example.test/start")
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError, match="cross-host"):
            handler.redirect_request(
                request,
                SimpleNamespace(),
                302,
                "Found",
                Message(),
                "https://other.test/target",
            )


def test_unexpected_content_type_is_rejected() -> None:
    opener = SimpleNamespace(open=lambda *_args, **_kwargs: FakeResponse(b"{}", "text/html"))
    with patch("rand_research.http_utils.urllib.request.build_opener", return_value=opener):
        with pytest.raises(ValueError, match="Content-Type"):
            request_bytes(
                "https://example.test/data",
                headers={},
                timeout_seconds=1,
                max_bytes=INTEGRATION_MAX_BYTES,
                allowed_content_types={"application/json"},
            )


@pytest.mark.parametrize("limit", [SOURCE_MAX_BYTES, INTEGRATION_MAX_BYTES])
def test_response_size_limit_is_enforced(limit: int) -> None:
    response = FakeResponse(b"x" * (limit + 1), "application/json")
    opener = SimpleNamespace(open=lambda *_args, **_kwargs: response)
    with patch("rand_research.http_utils.urllib.request.build_opener", return_value=opener):
        with pytest.raises(ValueError, match="exceeds"):
            request_bytes(
                "https://example.test/data",
                headers={},
                timeout_seconds=1,
                max_bytes=limit,
                allowed_content_types={"application/json"},
            )


def test_json_response_within_limit_is_returned() -> None:
    response = FakeResponse(b'{"status":"ok"}', "application/json; charset=utf-8")
    opener = SimpleNamespace(open=lambda *_args, **_kwargs: response)
    with patch("rand_research.http_utils.urllib.request.build_opener", return_value=opener):
        result = request_bytes(
            "https://example.test/data",
            headers={},
            timeout_seconds=1,
            max_bytes=INTEGRATION_MAX_BYTES,
            allowed_content_types={"application/json"},
        )
    assert result.body == b'{"status":"ok"}'
    assert result.charset == "utf-8"