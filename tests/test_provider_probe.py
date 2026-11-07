"""Unit tests for core/provider_probe.py and the provider_editor formatter boundary.

Tests probe_url branches (ACTIVE / INACTIVE / AUTH_FAILED / HTTP_ERROR / TIMEOUT /
ERROR / NOT_XTREAM), probe_all_urls ordering + on_result callback, and
format_probe_message's wording for each ProbeStatus.

No Qt required — provider_probe.py is intentionally UI-free.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from streamselect.core.provider_probe import (
    ProbeResult,
    ProbeStatus,
    probe_all_urls,
    probe_url,
)


# ── helpers ──────────────────────────────────────────────────────────────────

_URL = "http://provider.example.com"
_USER = "testuser"
_PASS = "testpass"


def _make_resp(status: int, json_data: dict | None = None) -> MagicMock:
    """Build a mock aiohttp response as an async context-manager."""
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data or {})
    # async context manager protocol
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _make_session(resp: MagicMock) -> MagicMock:
    """Build a mock aiohttp.ClientSession that returns resp from its get()."""
    get_cm = MagicMock()
    get_cm.__aenter__ = AsyncMock(return_value=resp)
    get_cm.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.get = MagicMock(return_value=get_cm)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


# ── probe_url: ACTIVE ─────────────────────────────────────────────────────────

def test_probe_url_active():
    resp = _make_resp(200, {"user_info": {"auth": 1, "status": "active"}})
    session = _make_session(resp)
    with patch("aiohttp.ClientSession", return_value=session):
        result = asyncio.run(probe_url(_URL, _USER, _PASS))
    assert result.success is True
    assert result.status is ProbeStatus.ACTIVE
    assert result.url == _URL
    assert result.latency_ms >= 0


# ── probe_url: INACTIVE (auth ok but account inactive) ───────────────────────

def test_probe_url_inactive():
    resp = _make_resp(200, {"user_info": {"auth": 1, "status": "Expired"}})
    session = _make_session(resp)
    with patch("aiohttp.ClientSession", return_value=session):
        result = asyncio.run(probe_url(_URL, _USER, _PASS))
    assert result.success is False
    assert result.status is ProbeStatus.INACTIVE
    assert result.detail == "Expired"


def test_probe_url_inactive_banned():
    resp = _make_resp(200, {"user_info": {"auth": 1, "status": "Banned"}})
    session = _make_session(resp)
    with patch("aiohttp.ClientSession", return_value=session):
        result = asyncio.run(probe_url(_URL, _USER, _PASS))
    assert result.status is ProbeStatus.INACTIVE
    assert result.detail == "Banned"


# ── probe_url: AUTH_FAILED ────────────────────────────────────────────────────

def test_probe_url_auth_failed():
    resp = _make_resp(200, {"user_info": {"auth": 0, "status": ""}})
    session = _make_session(resp)
    with patch("aiohttp.ClientSession", return_value=session):
        result = asyncio.run(probe_url(_URL, _USER, _PASS))
    assert result.success is False
    assert result.status is ProbeStatus.AUTH_FAILED
    assert result.detail == ""


# ── probe_url: HTTP_ERROR ─────────────────────────────────────────────────────

def test_probe_url_http_error_403():
    resp = _make_resp(403)
    session = _make_session(resp)
    with patch("aiohttp.ClientSession", return_value=session):
        result = asyncio.run(probe_url(_URL, _USER, _PASS))
    assert result.success is False
    assert result.status is ProbeStatus.HTTP_ERROR
    assert result.detail == "403"


def test_probe_url_http_error_503():
    resp = _make_resp(503)
    session = _make_session(resp)
    with patch("aiohttp.ClientSession", return_value=session):
        result = asyncio.run(probe_url(_URL, _USER, _PASS))
    assert result.status is ProbeStatus.HTTP_ERROR
    assert result.detail == "503"


# ── probe_url: TIMEOUT ────────────────────────────────────────────────────────

def test_probe_url_timeout():
    session = MagicMock()
    get_cm = MagicMock()
    get_cm.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
    get_cm.__aexit__ = AsyncMock(return_value=False)
    session.get = MagicMock(return_value=get_cm)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    with patch("aiohttp.ClientSession", return_value=session):
        result = asyncio.run(probe_url(_URL, _USER, _PASS))
    assert result.success is False
    assert result.status is ProbeStatus.TIMEOUT


# ── probe_url: ERROR (generic exception) ─────────────────────────────────────

def test_probe_url_connection_error():
    session = MagicMock()
    get_cm = MagicMock()
    get_cm.__aenter__ = AsyncMock(side_effect=Exception("Connection refused"))
    get_cm.__aexit__ = AsyncMock(return_value=False)
    session.get = MagicMock(return_value=get_cm)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    with patch("aiohttp.ClientSession", return_value=session):
        result = asyncio.run(probe_url(_URL, _USER, _PASS))
    assert result.success is False
    assert result.status is ProbeStatus.ERROR
    assert "Connection refused" in result.detail


def test_probe_url_error_detail_truncated():
    """detail is capped at 80 chars."""
    long_msg = "x" * 200
    session = MagicMock()
    get_cm = MagicMock()
    get_cm.__aenter__ = AsyncMock(side_effect=Exception(long_msg))
    get_cm.__aexit__ = AsyncMock(return_value=False)
    session.get = MagicMock(return_value=get_cm)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    with patch("aiohttp.ClientSession", return_value=session):
        result = asyncio.run(probe_url(_URL, _USER, _PASS))
    assert len(result.detail) <= 80


# ── probe_all_urls: ordering + on_result callback ────────────────────────────

def _make_probe_result(url: str, success: bool, latency_ms: int) -> ProbeResult:
    status = ProbeStatus.ACTIVE if success else ProbeStatus.TIMEOUT
    return ProbeResult(url, success, latency_ms, status)


def test_probe_all_urls_sorted_successes_first():
    """Successes come before failures; within each group, fastest first."""
    url_a = "http://a.example.com"
    url_b = "http://b.example.com"
    url_c = "http://c.example.com"

    async def fake_probe(url, username, password):
        return {
            url_a: _make_probe_result(url_a, True, 500),
            url_b: _make_probe_result(url_b, False, 10),
            url_c: _make_probe_result(url_c, True, 100),
        }[url]

    with patch("streamselect.core.provider_probe.probe_url", side_effect=fake_probe):
        results = asyncio.run(probe_all_urls([url_a, url_b, url_c], _USER, _PASS))

    assert results[0].url == url_c   # success, 100 ms
    assert results[1].url == url_a   # success, 500 ms
    assert results[2].url == url_b   # failure, 10 ms (failures always after successes)


def test_probe_all_urls_on_result_called_once_per_url():
    """on_result is invoked exactly once per URL."""
    urls = ["http://a.example.com", "http://b.example.com"]

    async def fake_probe(url, username, password):
        return _make_probe_result(url, True, 50)

    calls = []
    with patch("streamselect.core.provider_probe.probe_url", side_effect=fake_probe):
        asyncio.run(probe_all_urls(urls, _USER, _PASS, on_result=calls.append))

    assert len(calls) == 2
    called_urls = {r.url for r in calls}
    assert called_urls == set(urls)


def test_probe_all_urls_empty():
    """Empty URL list returns empty results list."""
    with patch("streamselect.core.provider_probe.probe_url") as mock_probe:
        results = asyncio.run(probe_all_urls([], _USER, _PASS))
    mock_probe.assert_not_called()
    assert results == []


# ── format_probe_message: one address's result in words ─────────────────────

from streamselect.gui.connection_diagnosis_text import format_probe_message  # noqa: E402


def _fmt(status: ProbeStatus, detail: str = "", ms: int = 0) -> str:
    return format_probe_message(ProbeResult(_URL, status is ProbeStatus.ACTIVE, ms, status, detail))


def test_format_active():
    assert _fmt(ProbeStatus.ACTIVE, ms=123) == "Active  123 ms"


def test_format_inactive():
    assert _fmt(ProbeStatus.INACTIVE, "Expired") == "Account Expired"


@pytest.mark.parametrize(("status", "detail", "says"), [
    (ProbeStatus.AUTH_FAILED, "", "Wrong login"),
    (ProbeStatus.NOT_XTREAM, "", "Wrong address"),
    (ProbeStatus.HTTP_ERROR, "403", "Refused (403)"),
    (ProbeStatus.HTTP_ERROR, "404", "Not found (404)"),
    (ProbeStatus.HTTP_ERROR, "502", "Server error (502)"),
    (ProbeStatus.TIMEOUT, "", "No answer"),
    (ProbeStatus.ERROR, "Connection refused", "Can't connect"),
])
def test_a_failure_says_its_cause_not_only_its_code(status, detail, says):
    """A user (Q6): a failure says why in words. The code stays as evidence."""
    assert _fmt(status, detail) == says


def test_format_unknown_http_code_still_shows_the_code():
    assert _fmt(ProbeStatus.HTTP_ERROR, "302") == "HTTP 302"


def test_format_error_empty_detail():
    assert _fmt(ProbeStatus.ERROR, "") == "Can't connect"


def test_probe_url_non_json_answer_is_not_an_xtream_server():
    """A 200 carrying a web page is the wrong address, not a network error."""
    resp = _make_resp(200)
    resp.json = AsyncMock(side_effect=ValueError("Expecting value"))
    with patch("aiohttp.ClientSession", return_value=_make_session(resp)):
        result = asyncio.run(probe_url(_URL, _USER, _PASS))
    assert result.success is False
    assert result.status is ProbeStatus.NOT_XTREAM
