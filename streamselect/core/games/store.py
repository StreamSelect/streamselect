"""Run the game finder over the database and store what it finds.

The one entry point is :func:`refresh_games`: read the live channels of the
visible sources and the guide programmes in the window, find each enabled
league's games, and replace that league's stored games. Runs off the UI
thread (the caller's executor); the finder itself never touches the database.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Mapping, Optional

from loguru import logger
from sqlalchemy import delete, or_, select

from streamselect.core.database import Database, ChannelDB, EpgProgramDB
from streamselect.core.epg_utils import now_utc, to_local
from streamselect.core.event_datetime import DEFAULT_EVENT_DURATION
from streamselect.core.games import tuning
from streamselect.core.games.finder import (
    GUIDE, ListingIn, Memory, PlayIn, SportSettings, _learn_clocks, find_games,
)
from streamselect.core.games.listing_text import (
    MATCHUP_LIKE_PATTERNS, NOT_PLAIN_GLOB, league_matcher, norm,
)
from streamselect.core.games.models import GameDB, GameFeedDB, GameFinderMemoryDB
from streamselect.core.playback_models import PlaybackEventDB
from streamselect.core.repositories.provider import ProviderRepository
from streamselect.core import sports_catalog


def _league_words() -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """(sport, league, words) for every league the finder runs (the one sports
    list, ``finder: listed`` or ``trial``)."""
    return tuple((lg.sport, lg.name, lg.words) for lg in sports_catalog.finder_leagues() if lg.words)


def enabled_leagues(overrides: Optional[Mapping] = None) -> tuple[SportSettings, ...]:
    """The leagues the finder runs for (``finder: listed | trial`` in the one
    sports list, core/sports_catalog.py), each with its sport's numbers: the sport's defaults, then the
    user's own choices (*overrides*, ``Config.sport_settings_overrides``; the core
    never reads Config itself)."""
    per_sport = {sport: tuning.settings_kwargs(tuning.values(sport, overrides))
                 for sport, _league, _words in _league_words()}
    return tuple(SportSettings(sport, league, words, **per_sport[sport])
                 for sport, league, words in _league_words())


def sport_settings(overrides: Optional[Mapping] = None) -> dict[str, SportSettings]:
    """sport -> its settings, in listed order.

    The one place a reader gets "the sports there are": the Sports view, the
    Watch Alerts Sports group and the event-alert notifier all loop over this.
    """
    out: dict[str, SportSettings] = {}
    for league in enabled_leagues(overrides):
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
        "usual_starts": sorted(u.isoformat() for u in m.usual_starts),
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
    m.usual_starts = {datetime.fromisoformat(u) for u in (d or {}).get("usual_starts", [])}
    return m


def _recent_plays(session, now: datetime, days: int) -> list[PlayIn]:
    """Plays that showed a picture in the last *days*, each under the channel name
    it had then, on the viewer's local day."""
    since = now - timedelta(days=days)
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

    return or_(
        ChannelDB.category.in_(categories),
        ChannelDB.name.op("GLOB")(NOT_PLAIN_GLOB),
        *(ChannelDB.name.like(p) for p in MATCHUP_LIKE_PATTERNS),
        *(_name_like(w) for w in words),
    )


def _name_like(word: str):
    """A channel name containing *word* (LIKE, so a substring the finder narrows again)."""
    escaped = word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return ChannelDB.name.like(f"%{escaped}%", escape="\\")


def _guide_in_window(settings: SportSettings, now: datetime):
    """Guide programmes in the league's window naming one of its words."""
    return (EpgProgramDB.start_time.between(now - max(settings.window_back, settings.replay_within),
                                            now + settings.window_ahead),
            or_(*(EpgProgramDB.title.ilike(f"%{w}%") for w in settings.words)))


def _leagues_named(session, leagues, now: datetime, plays) -> set[str]:
    """The leagues some listing, guide programme or recent play names.

    A game needs a listing that names its league (the finder's seed), so a league
    nobody names finds nothing, and its run (every matchup-shaped listing read and
    normalised, ~0.9 s on 20,000 listings) is skipped. Thirty-odd basketball
    leagues run each refresh; most name nothing most of the year (2026-11-23).
    One read for all leagues: the channels and guide titles holding any league's
    word, matched per league like the finder. Over-inclusive by design: hidden
    sources count, the widest window is used, and a name LIKE cannot judge
    (beyond plain ASCII) is read too.
    """
    if not leagues:
        return set()
    live = ChannelDB.media_type == "live"
    words = sorted({w for settings in leagues for w in settings.words})
    texts = [c for (c,) in session.execute(select(ChannelDB.category).where(live).distinct()) if c]
    texts += session.execute(select(ChannelDB.name).where(
        live, or_(ChannelDB.name.op("GLOB")(NOT_PLAIN_GLOB), *(_name_like(w) for w in words)))).scalars()
    back = max(max(st.window_back, st.replay_within) for st in leagues)
    ahead = max(st.window_ahead for st in leagues)
    texts += session.execute(select(EpgProgramDB.title).where(
        EpgProgramDB.start_time.between(now - back, now + ahead),
        or_(*(EpgProgramDB.title.ilike(f"%{w}%") for w in words)))).scalars()
    texts = [norm(t) for t in texts if t] + [norm(p.title) for p in plays]
    named = set()
    for st in leagues:
        league = league_matcher(st.words)
        if not all(w.isascii() and w.isprintable() for w in st.words) or any(map(league.search, texts)):
            named.add(_finder_key(st))
    return named


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
        # Back as far as the replay rule looks (as much as the guide keeps): the
        # original of a rerun is then found even on a league's first run (finder).
        .where(*_guide_in_window(settings, now))).all()
    listings += [ListingIn(GUIDE, cname or epg_id or "", title or "", cdb, start)
                 for pid, cdb, epg_id, cname, title, start in guide if pid not in hidden]
    return listings


def refresh_games(db: Database, now: datetime | None = None,
                  overrides: Optional[Mapping] = None) -> dict[str, int]:
    """Find every enabled league's games and replace them in the database.

    *overrides*: the user's Sports settings (``Config.sport_settings_overrides``).

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
        leagues = enabled_leagues(overrides)
        plays = _recent_plays(session, now, max((s.most_watched_days for s in leagues), default=0))
        named = _leagues_named(session, leagues, now, plays)
        stored = {f"{sport}/{league}" for sport, league in
                  session.execute(select(GameDB.sport, GameDB.league).distinct())}
    for settings in leagues:
        t0 = time.monotonic()
        key = _finder_key(settings)
        if key not in named and key not in stored:
            counts[key] = 0         # nothing names it and nothing of it is stored: no change
            continue
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
