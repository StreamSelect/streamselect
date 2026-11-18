"""Run the game finder over the database and store what it finds.

The one entry point is :func:`refresh_games`: read the live channels of the
visible sources and the guide programmes in the window, find each enabled
league's games, and replace that league's stored games. Runs off the UI
thread (the caller's executor); the finder itself never touches the database.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from functools import lru_cache

import yaml
from loguru import logger
from sqlalchemy import delete, or_, select

from streamselect.core.database import Database, ChannelDB, EpgProgramDB
from streamselect.core.epg_utils import now_utc, to_local
from streamselect.core.event_datetime import DEFAULT_EVENT_DURATION
from streamselect.core.games.finder import (
    GUIDE, WATCH_WINDOW_DAYS, ListingIn, Memory, PlayIn, SportSettings, _learn_clocks, find_games,
)
from streamselect.core.games.listing_text import (
    MATCHUP_LIKE_PATTERNS, NOT_PLAIN_GLOB, league_matcher, norm,
)
from streamselect.core.games.models import GameDB, GameFeedDB, GameFinderMemoryDB
from streamselect.core.playback_models import PlaybackEventDB
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
        "watched": [[pid, day, secs] for pid, (day, secs) in m.watched.items()],
    }


def _memory_from_json(d: dict | None) -> Memory:
    m = Memory()
    for src, coll, game, diff, seen in (d or {}).get("clock_samples", []):
        m.clock_samples.setdefault((src, coll), {})[game] = (int(diff), datetime.fromisoformat(seen))
    for cid, name, seen in (d or {}).get("first_seen", []):
        m.first_seen[(cid, name)] = datetime.fromisoformat(seen)
    for title, starts in (d or {}).get("confirmed", {}).items():
        m.confirmed[title] = {datetime.fromisoformat(u) for u in starts}
    for pid, day, secs in (d or {}).get("watched", []):
        m.watched[int(pid)] = (str(day), int(secs))
    return m


def _recent_plays(session, now: datetime) -> list[PlayIn]:
    """Plays that showed a picture in the last :data:`WATCH_WINDOW_DAYS`, each under
    the channel name it had then, on the viewer's local day."""
    since = now - timedelta(days=WATCH_WINDOW_DAYS)
    rows = session.execute(
        select(PlaybackEventDB.id, PlaybackEventDB.title, PlaybackEventDB.started_at,
               PlaybackEventDB.seconds_watched)
        .where(PlaybackEventDB.started_at >= since,
               PlaybackEventDB.outcome.in_(("started", "dropped")))).all()
    cap = int(DEFAULT_EVENT_DURATION.total_seconds())      # one play counts at most one event
    return [PlayIn(pid, title or "", to_local(at).date().isoformat(), min(int(secs or 0), cap))
            for pid, title, at, secs in rows]


def load_league_watch(session) -> dict[str, tuple[frozenset[str], int]]:
    """league key ("hockey/NHL") -> (the local days it was watched, seconds watched),
    from each league's stored memory: the "Most watched" order's input."""
    out = {}
    for row in session.query(GameFinderMemoryDB).all():
        watched = _memory_from_json(row.memory).watched.values()
        out[row.finder] = (frozenset(day for day, _ in watched), sum(secs for _, secs in watched))
    return out


def _could_name_a_game(session, settings: SportSettings):
    """SQL for the live channels the finder can use: one in a category naming the
    league, or one whose name names the league or states a matchup. Every other
    channel is dropped by the finder unread, so leaving it in the database
    changes no game; it was 60% of 54,000 rows read and normalised on every run,
    under a UI thread building widgets (2026-11-17).

    Categories are few (hundreds), so the finder's own whole-word rule runs on
    each distinct one here. Names are not, so for them this is only a necessary
    condition: LIKE is a substring test the finder narrows again, and a name LIKE
    cannot judge (anything beyond printable ASCII) is kept. Returns None (read
    every live channel) when a league word is itself beyond plain ASCII.
    """
    words = list(settings.words)
    if not all(w.isascii() and w.isprintable() for w in words):
        return None
    league = league_matcher(words)
    categories = [c for (c,) in session.execute(
        select(ChannelDB.category).where(ChannelDB.media_type == "live").distinct())
        if c and league.search(norm(c))]

    def like(word):
        escaped = word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return ChannelDB.name.like(f"%{escaped}%", escape="\\")

    return or_(
        ChannelDB.category.in_(categories),
        ChannelDB.name.op("GLOB")(NOT_PLAIN_GLOB),
        *(ChannelDB.name.like(p) for p in MATCHUP_LIKE_PATTERNS),
        *(like(w) for w in words),
    )


def _read_listings(session, settings: SportSettings, now: datetime, hidden: set[str]) -> list[ListingIn]:
    """The live channels of the visible sources that could name a game, plus the
    guide programmes naming the league."""
    query = (select(ChannelDB.id, ChannelDB.provider_id, ChannelDB.category, ChannelDB.name)
             .where(ChannelDB.media_type == "live"))
    narrow = _could_name_a_game(session, settings)
    rows = session.execute(query if narrow is None else query.where(narrow)).all()
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
    # Every league's learned clocks, so a collection one league never learned can
    # borrow what another's run did (finder._with_borrowed). Re-learned from the
    # stored samples: a clock is a property of the collection, not the league.
    with db.session_scope(commit=False) as session:
        known = tuple(c for row in session.query(GameFinderMemoryDB).all()
                      for c in _learn_clocks(_memory_from_json(row.memory).clock_samples).values())
        plays = _recent_plays(session, now)
    for settings in enabled_leagues():
        t0 = time.monotonic()
        key = _finder_key(settings)
        with db.session_scope(commit=False) as session:
            hidden = set(ProviderRepository(session).get_hidden_provider_ids())
            listings = _read_listings(session, settings, now, hidden)
            row = session.get(GameFinderMemoryDB, key)
            memory = _memory_from_json(row.memory if row else None)
        games, memory, clocks = find_games(listings, settings, now, memory, known, plays)
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
                    sum(c.learned and not c.borrowed_from for c in clocks), time.monotonic() - t0)
        for c in clocks:
            if c.borrowed_from and any(g.feeds and any(f.collection == c.collection and f.time_from == "borrowed"
                                                          for f in g.feeds) for g in games):
                logger.info("Games {}: {} has no clock of its own; borrowed {:+d} min from {}",
                            key, c.collection, c.offset_min, c.borrowed_from)
    return counts
