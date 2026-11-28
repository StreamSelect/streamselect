"""The game a channel carries now: its sport, read through ``game_feeds``.

A sports row stored as a kind rather than a sport (``sports_catalog``: an
event slot, a many-sports network, an unidentified matchup) says nothing about
what it shows. When the game finder has placed a game on it, that game's sport
and league are what it is showing, so the channel list shows them. They are
read here and never written onto the channel (design "One Sports List",
OL-Q13): a slot carries a different game every day, and a stored sport would
be wrong by tomorrow. Measured 2026-11-27: 83 unknown matchup rows and 30
network rows carried a game; event slots carried none.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sqlalchemy import select

from streamselect.core.epg_utils import local_date
from streamselect.core.event_datetime import DEFAULT_EVENT_DURATION
from streamselect.core.games.models import GameDB, GameFeedDB

#: The levels the Sports view lists by default (core/games/read.py load_games).
_MAX_LEVEL = 2


@dataclass(frozen=True)
class CarriedGame:
    """The game on one channel: what its sport cell shows, and the tooltip's why."""

    sport: str
    league: str
    title: str          # "Edmonton Oilers vs Calgary Flames"
    start_utc: datetime


def pick(starts: list[tuple[datetime, CarriedGame]], now: datetime) -> CarriedGame | None:
    """Of one channel's games, the one it carries: the latest started and not yet
    past the usual event length, else the next to start today (local)."""
    on = [(s, g) for s, g in starts if s <= now < s + DEFAULT_EVENT_DURATION]
    if on:
        return max(on, key=lambda t: t[0])[1]
    today = local_date(now)              # *now*'s day, never the real clock's
    later = [(s, g) for s, g in starts if s > now and local_date(s) == today]
    return min(later, key=lambda t: t[0])[1] if later else None


def carried_games(session, channel_ids: Iterable[str], now: datetime) -> dict[str, CarriedGame]:
    """channel id -> the game it carries now, for the channels that carry one.

    One query for the whole page. Only channels the finder placed a game on
    appear; the caller passes a page's kind rows, never every row.
    """
    ids = sorted({c for c in channel_ids if c})
    if not ids:
        return {}
    rows = session.execute(
        select(GameFeedDB.channel_id, GameDB.sport, GameDB.league, GameDB.team_a,
               GameDB.team_b, GameDB.start_utc)
        .join(GameDB, GameDB.id == GameFeedDB.game_id)
        .where(GameFeedDB.channel_id.in_(ids), GameDB.level <= _MAX_LEVEL)).all()
    per: dict[str, list[tuple[datetime, CarriedGame]]] = {}
    for cid, sport, league, a, b, start in rows:
        per.setdefault(cid, []).append((start, CarriedGame(sport, league, f"{a} vs {b}", start)))
    out = {}
    for cid, starts in per.items():
        game = pick(starts, now)
        if game is not None:
            out[cid] = game
    return out
