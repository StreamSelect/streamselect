"""Run the game finder over the database and store what it finds.

The one entry point is :func:`refresh_games`: read the live channels of the
visible sources and the guide programmes in the window, find each enabled
league's games, and replace that league's stored games. Runs off the UI
thread (the caller's executor); the finder itself never touches the database.
"""

from __future__ import annotations

import time
from datetime import datetime
from functools import lru_cache

import yaml
from loguru import logger
from sqlalchemy import delete, or_, select

from streamselect.core.database import Database, ChannelDB, EpgProgramDB
from streamselect.core.epg_utils import now_utc
from streamselect.core.games.finder import GUIDE, ListingIn, Memory, SportSettings, find_games
from streamselect.core.games.models import GameDB, GameFeedDB, GameFinderMemoryDB
from streamselect.core.repositories.provider import ProviderRepository
from streamselect.core.special_content import _BUNDLED_DEFINITIONS


@lru_cache(maxsize=1)
def enabled_leagues() -> tuple[SportSettings, ...]:
    """The leagues the finder runs for, from ``game_finder_leagues`` in the bundled definitions."""
    with open(_BUNDLED_DEFINITIONS) as f:
        data = yaml.safe_load(f) or {}
    return tuple(
        SportSettings(sport, league, tuple(str(w) for w in words))
        for sport, leagues in (data.get("game_finder_leagues") or {}).items()
        for league, words in (leagues or {}).items() if words)


def sport_settings() -> dict[str, SportSettings]:
    """sport -> its settings (the first listed league's lengths), in listed order.

    The one place a reader gets "the sports there are": the Sports view, the
    Watch Alerts Sports group and the event-alert notifier all loop over this.
    """
    out: dict[str, SportSettings] = {}
    for league in enabled_leagues():
        out.setdefault(league.sport, league)
    return out


def _finder_key(s: SportSettings) -> str:
    return f"{s.sport}/{s.league}"


def _memory_to_json(m: Memory) -> dict:
    return {
        "clock_samples": [[src, coll, game, diff, seen.isoformat()]
                          for (src, coll), games in m.clock_samples.items()
                          for game, (diff, seen) in games.items()],
        "first_seen": [[cid, name, seen.isoformat()] for (cid, name), seen in m.first_seen.items()],
        "confirmed": {title: sorted(u.isoformat() for u in starts) for title, starts in m.confirmed.items()},
    }


def _memory_from_json(d: dict | None) -> Memory:
    m = Memory()
    for src, coll, game, diff, seen in (d or {}).get("clock_samples", []):
        m.clock_samples.setdefault((src, coll), {})[game] = (int(diff), datetime.fromisoformat(seen))
    for cid, name, seen in (d or {}).get("first_seen", []):
        m.first_seen[(cid, name)] = datetime.fromisoformat(seen)
    for title, starts in (d or {}).get("confirmed", {}).items():
        m.confirmed[title] = {datetime.fromisoformat(u) for u in starts}
    return m


def _read_listings(session, settings: SportSettings, now: datetime, hidden: set[str]) -> list[ListingIn]:
    """Every live channel of the visible sources, plus the guide programmes naming the league."""
    rows = session.execute(
        select(ChannelDB.id, ChannelDB.provider_id, ChannelDB.category, ChannelDB.name)
        .where(ChannelDB.media_type == "live")).all()
    listings = [ListingIn(pid, cat or "", name or "", cid)
                for cid, pid, cat, name in rows if pid not in hidden]
    # SQL narrows by substring; the finder applies the whole-word rule itself.
    guide = session.execute(
        select(EpgProgramDB.provider_id, EpgProgramDB.channel_db_id, EpgProgramDB.channel_epg_id,
               EpgProgramDB.channel_name, EpgProgramDB.title, EpgProgramDB.start_time)
        .where(EpgProgramDB.start_time.between(now - settings.window_back, now + settings.window_ahead))
        .where(or_(*(EpgProgramDB.title.ilike(f"%{w}%") for w in settings.words)))).all()
    listings += [ListingIn(GUIDE, cname or epg_id or "", title or "", cdb, start)
                 for pid, cdb, epg_id, cname, title, start in guide if pid not in hidden]
    return listings


def refresh_games(db: Database, now: datetime | None = None) -> dict[str, int]:
    """Find every enabled league's games and replace them in the database.

    Returns:
        league key -> number of Level 1 games stored (for the log line).
    """
    now = now or now_utc()
    counts: dict[str, int] = {}
    for settings in enabled_leagues():
        t0 = time.monotonic()
        key = _finder_key(settings)
        with db.session_scope(commit=False) as session:
            hidden = set(ProviderRepository(session).get_hidden_provider_ids())
            listings = _read_listings(session, settings, now, hidden)
            row = session.get(GameFinderMemoryDB, key)
            memory = _memory_from_json(row.memory if row else None)
        games, memory, clocks = find_games(listings, settings, now, memory)
        with db.session_scope(background=True) as session:
            old = select(GameDB.id).where(GameDB.sport == settings.sport, GameDB.league == settings.league)
            session.execute(delete(GameFeedDB).where(GameFeedDB.game_id.in_(old)))
            session.execute(delete(GameDB).where(GameDB.sport == settings.sport,
                                                 GameDB.league == settings.league))
            for g in games:
                row = GameDB(sport=g.sport, league=g.league, team_a=g.team_a, team_b=g.team_b,
                             start_utc=g.start_utc, level=g.level, replay=g.replay,
                             collections=g.collections, found_at=now, home_team=g.home or None)
                row.feeds = [GameFeedDB(channel_id=f.channel_id, source=f.source, collection=f.collection,
                                        name=f.name, from_guide=f.from_guide, time_from=f.time_from,
                                        start_utc=f.start_utc, counts=f.counts) for f in g.feeds]
                session.add(row)
            session.merge(GameFinderMemoryDB(finder=key, memory=_memory_to_json(memory), updated_at=now))
        counts[key] = sum(g.level == 1 for g in games)
        logger.info("Games {}: {} found ({} at level 1) from {:,} listings, {} clocks learned, {:.1f}s",
                    key, len(games), counts[key], len(listings),
                    sum(c.learned for c in clocks), time.monotonic() - t0)
    return counts
