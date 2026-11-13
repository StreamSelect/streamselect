"""Reading stored games for a screen: frozen DTOs, the game's state now, its best feed.

Screens never parse a channel name for a game: everything here reads what
:mod:`streamselect.core.games.store` wrote. Hidden sources are applied at
read time too, because a source switched off after the last finder run must
vanish now, not at the next refresh.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Optional

from sqlalchemy import case, func, select

from streamselect.core.category_headings import split_head
from streamselect.core.database import ChannelDB
from streamselect.core.event_datetime import DEFAULT_EVENT_DURATION, event_is_on_now
from streamselect.core.games.finder import SportSettings
from streamselect.core.games.models import GameDB, GameEndDB, GameFeedDB
from streamselect.core.playback_models import PlaybackEventDB
from streamselect.core.region_codes import leading_country

UPCOMING, ON_NOW, ENDING, OVER = "upcoming", "on_now", "ending", "over"


@dataclass(frozen=True)
class GameFeedDTO:
    channel_id: Optional[str]
    name: str
    collection: str
    from_guide: bool
    time_from: str = ""          # "zone", "clock", "guide", or "" (joined by its teams alone)
    #: The CHANNEL's own source and collection (a guide feed's ``collection`` is the
    #: guide channel's name), its stored region and quality, and the station label.
    provider_id: str = ""
    channel_collection: str = ""
    region: str = ""
    quality: str = ""

    @property
    def collection_key(self) -> str:
        """``"<source>|<collection>"`` — what a preference or a hide sticks to: slot
        channel ids change between refreshes, the collection does not."""
        return f"{self.provider_id}|{self.channel_collection}"

    @property
    def station(self) -> str:
        """The collection without its region head: "US| ESPN+ PPV VIP" -> "ESPN+ PPV VIP",
        "SWEDEN TELIA PLAY" -> "TELIA PLAY" (category_headings / region_codes)."""
        # NFKC folds the superscript letters some collections use ("NORWAY ᴳᴼᴸᴰ ᴿᴬᵂ"),
        # which otherwise render tiny — the same folding the finder reads names with.
        c = unicodedata.normalize("NFKC", self.channel_collection or self.collection)
        return split_head(c)[1] or (leading_country(c) or ("", c))[1] or c


#: Best feed first: a listing that states its own time with a zone is the most
#: explicit about being this game, then a learned clock, then one with no time,
#: and a guide link last (the guide is the least reliable input).
_FEED_RANK = {"zone": 0, "clock": 1, "": 2, "guide": 3}


@dataclass(frozen=True)
class GameDTO:
    id: int
    sport: str
    league: str
    team_a: str
    team_b: str
    start_utc: datetime
    level: int
    replay: bool
    collections: int
    feeds: tuple[GameFeedDTO, ...]
    #: Feeds the user hid from this league's games (counted on the card, never silently gone).
    hidden: tuple[GameFeedDTO, ...] = ()
    #: When the user marked it finished (UTC), else None.
    ended_at: Optional[datetime] = None

    @property
    def league_key(self) -> str:
        """``"hockey/NHL"`` — the key preferences and hides are kept under."""
        return f"{self.sport}/{self.league}"

    @property
    def title(self) -> str:
        return f"{self.team_a} vs {self.team_b}"

    @property
    def playable(self) -> tuple[GameFeedDTO, ...]:
        """Feeds that open a channel (a guide programme with no channel link cannot)."""
        return tuple(f for f in self.feeds if f.channel_id)


def game_state(game: GameDTO, now: datetime, settings: SportSettings) -> str:
    """upcoming / on_now / ending (past its usual length) / over (past the long limit)."""
    start = game.start_utc
    if game.ended_at is not None and now >= game.ended_at:
        return OVER                      # the user said so (Mark as finished)
    if now < start:
        return UPCOMING
    # The one "is it on" rule (event_datetime), given the sport's lengths as the stop.
    if event_is_on_now(start, start + settings.usual_length, now):
        return ON_NOW
    if event_is_on_now(start, start + settings.long_limit, now):
        return ENDING
    return OVER


def best_feed(game: GameDTO) -> Optional[GameFeedDTO]:
    """The feed a click on the game plays: the first of :attr:`GameDTO.playable`
    once :func:`arrange_feeds` has ordered them."""
    feeds = game.playable
    return feeds[0] if feeds else None


#: collection key -> (last WATCHED play or None, seconds watched, plays) from the play log.
WatchHistory = dict[str, tuple[Optional[datetime], int, int]]

#: A play shorter than this is a bail, not a choice: it does not make its collection
#: "the one you last watched". Owner, 2026-11-12: a 27 s try of one channel took over
#: a game whose card should have offered the channel then watched for minutes; the play
#: log separates bails (seconds) from watches (minutes) cleanly. A play still running
#: (no seconds yet) counts as watched.
WATCHED_MIN_SECONDS = 60
_PLAY_CAP_S = int(DEFAULT_EVENT_DURATION.total_seconds())


def arrange_feeds(game: GameDTO, prefs: dict, history: WatchHistory) -> GameDTO:
    """Hide what the user hid for this league, then order the rest (owner, SV-Q27/Q28).

    Order: the user's PREFERRED collection; else the collection they last watched
    that carries this game; then most minutes watched, most plays (per collection,
    because slot channel ids change); then how explicitly the listing states its
    time (``_FEED_RANK``). Pure; ``prefs`` is ``Config.game_channel_prefs`` for the league.
    """
    hidden_ids = set(prefs.get("hidden_channels") or ())
    hidden_colls = set(prefs.get("hidden_collections") or ())
    keep, gone = [], []
    for f in game.feeds:
        (gone if f.channel_id in hidden_ids or f.collection_key in hidden_colls else keep).append(f)
    preferred = prefs.get("preferred")
    watched = [f.collection_key for f in keep if history.get(f.collection_key, (None,))[0] is not None]
    last = max(watched, key=lambda k: history[k][0]) if watched else None

    def key(f: GameFeedDTO):
        _last, secs, plays = history.get(f.collection_key, (None, 0, 0))
        return (f.collection_key != preferred, f.collection_key != last, -secs, -plays,
                _FEED_RANK.get(f.time_from, 2))
    return replace(game, feeds=tuple(sorted(keep, key=key)), hidden=tuple(gone))


def mark_finished(session, game: GameDTO, ended_at: datetime) -> None:
    """Record that *game* is over, as of *ended_at* (UTC). Idempotent: a second mark moves the time."""
    session.merge(GameEndDB(league_key=game.league_key, team_a=game.team_a, team_b=game.team_b,
                            start_utc=game.start_utc, ended_at=ended_at))


def load_watch_history(session) -> WatchHistory:
    """Plays that showed a picture, grouped by the played channel's source and collection.

    The "last watched" time counts only plays of at least :data:`WATCHED_MIN_SECONDS`
    (or still running); minutes and plays count everything that showed a picture.
    """
    watched = PlaybackEventDB.seconds_watched.is_(None) | (PlaybackEventDB.seconds_watched >= WATCHED_MIN_SECONDS)
    rows = session.execute(
        select(ChannelDB.provider_id, ChannelDB.category,
               func.max(case((watched, PlaybackEventDB.started_at), else_=None)),
               # One play counts at most one event's length: rows stored before ledger D73's
               # fix can hold a broadcast-clock jump (one read 92,693 s).
               func.coalesce(func.sum(func.min(PlaybackEventDB.seconds_watched, _PLAY_CAP_S)), 0),
               func.count())
        .join(ChannelDB, ChannelDB.id == PlaybackEventDB.channel_id)
        .where(PlaybackEventDB.outcome.in_(("started", "dropped")))
        .group_by(ChannelDB.provider_id, ChannelDB.category)).all()
    return {f"{pid}|{cat or ''}": (last, int(secs), int(n)) for pid, cat, last, secs, n in rows}


def load_games(session, sport: str, hidden_provider_ids: set[str],
               min_level: int = 1, max_level: int = 2) -> list[GameDTO]:
    """Stored games of *sport* at levels min..max, feeds of hidden sources removed.

    A game left with no playable feed is dropped: there is nothing to watch.
    Ordered by start time.
    """
    rows = session.execute(
        select(GameDB).where(GameDB.sport == sport, GameDB.level.between(min_level, max_level))
        .order_by(GameDB.start_utc, GameDB.team_a)).scalars().all()
    if not rows:
        return []
    feed_rows = session.execute(select(GameFeedDB).where(GameFeedDB.game_id.in_([g.id for g in rows]))
                                .order_by(GameFeedDB.id)).scalars().all()
    chan = {cid: rest for cid, *rest in session.execute(
        select(ChannelDB.id, ChannelDB.provider_id, ChannelDB.category,
               ChannelDB.detected_region, ChannelDB.detected_quality)
        .where(ChannelDB.id.in_({f.channel_id for f in feed_rows if f.channel_id})))}
    feeds: dict[int, list[GameFeedDTO]] = {}
    for f in feed_rows:
        pid, cat, region, quality = chan.get(f.channel_id, (f.source, f.collection, "", ""))
        if pid in hidden_provider_ids:
            continue
        feeds.setdefault(f.game_id, []).append(
            GameFeedDTO(f.channel_id, f.name, f.collection, f.from_guide,
                        "guide" if f.from_guide else f.time_from,
                        pid or "", cat or "", region or "", quality or ""))
    for gid, fs in feeds.items():
        fs.sort(key=lambda f: _FEED_RANK.get(f.time_from, 2))
        # One feed per channel: a guide programme on a channel already listed by
        # name adds no second place to watch (the named listing ranks first).
        seen: set = set()
        feeds[gid] = [f for f in fs if not f.channel_id or not (f.channel_id in seen or seen.add(f.channel_id))]
    ends = {(e.league_key, e.team_a, e.team_b, e.start_utc): e.ended_at
            for e in session.execute(select(GameEndDB)).scalars()}
    out = []
    for g in rows:
        dto = GameDTO(g.id, g.sport, g.league, g.team_a, g.team_b, g.start_utc, g.level,
                      g.replay, g.collections, tuple(feeds.get(g.id, ())),
                      ended_at=ends.get((f"{g.sport}/{g.league}", g.team_a, g.team_b, g.start_utc)))
        if dto.playable:
            out.append(dto)
    return out
