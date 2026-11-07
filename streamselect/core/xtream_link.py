"""Read an Xtream account out of a link a provider hands out.

Providers usually give a new customer an "M3U link" rather than a server
address and a login, e.g.::

    http://example.com:8080/get.php?username=joe&password=s3cret&type=m3u_plus

StreamSelect has no M3U source type, but a link of this shape IS an Xtream account:
the part before the path is the server address and the query carries the
login. Splitting it here lets Add Source accept what the user was actually
given (user report), without pretending to read arbitrary playlists.

UI-free and English-free, like ``provider_probe``.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit, urlunsplit

#: Paths an Xtream panel serves that carry the login in the query string.
_ACCOUNT_PATHS = ("get.php", "player_api.php", "xmltv.php", "panel_api.php")


@dataclass(frozen=True)
class XtreamLink:
    """An Xtream account found in a link.

    Attributes:
        server: The server address — scheme, host and port, no path.
        username: The login name from the link.
        password: The password from the link.
    """

    server: str
    username: str
    password: str


def parse_xtream_link(text: str) -> XtreamLink | None:
    """Split a provider's M3U / API link into server address and login.

    Args:
        text: Whatever the user pasted.

    Returns:
        The account, or ``None`` when *text* is not such a link (a plain
        server address, say) — the caller then treats it as an address.
    """
    raw = (text or "").strip()
    if not raw:
        return None
    parts = urlsplit(raw if "://" in raw else f"http://{raw}")
    if not parts.netloc or parts.path.rstrip("/").rsplit("/", 1)[-1] not in _ACCOUNT_PATHS:
        return None
    query = parse_qs(parts.query, keep_blank_values=True)
    username = (query.get("username") or [""])[0]
    password = (query.get("password") or [""])[0]
    if not username or not password:
        return None
    # Any directory in front of get.php stays part of the server address: a
    # panel behind a reverse proxy serves its API under that prefix too.
    prefix = parts.path.rstrip("/").rsplit("/", 1)[0]
    server = urlunsplit((parts.scheme, parts.netloc, prefix, "", ""))
    return XtreamLink(server=server, username=username, password=password)
