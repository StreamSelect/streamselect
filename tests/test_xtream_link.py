"""A provider's M3U link is an Xtream account: Add Source takes all three parts.

User report: Add Source accepts the M3U link a provider sends. StreamSelect has
no M3U source type; a get.php link carries the server address and the login,
and that is all an Xtream source needs.
"""
from __future__ import annotations

import pytest

from streamselect.core.xtream_link import parse_xtream_link


def test_an_m3u_link_splits_into_server_and_login() -> None:
    link = parse_xtream_link(
        "http://example.com:8080/get.php?username=joe&password=p%26ss%23&type=m3u_plus&output=ts")
    assert link is not None
    assert link.server == "http://example.com:8080"
    assert (link.username, link.password) == ("joe", "p&ss#")


def test_a_path_in_front_of_get_php_stays_in_the_server_address() -> None:
    link = parse_xtream_link("https://example.com/iptv/get.php?username=a&password=b")
    assert link is not None and link.server == "https://example.com/iptv"


def test_a_link_without_a_scheme_is_read_as_http() -> None:
    link = parse_xtream_link("example.com:80/player_api.php?username=a&password=b")
    assert link is not None and link.server == "http://example.com:80"


@pytest.mark.parametrize("text", [
    "http://example.com:8080",                          # a plain server address
    "http://example.com/get.php?username=a",            # no password
    "http://example.com/live/a/b/1.ts",                 # a stream, not an account
    "",
])
def test_anything_else_is_left_as_an_address(text: str) -> None:
    assert parse_xtream_link(text) is None
