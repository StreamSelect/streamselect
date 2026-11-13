"""Reading stored games for a screen: frozen DTOs, the game's state now, its best feed.

Screens never parse a channel name for a game: everything here reads what
:mod:`streamselect.core.games.store` wrote. Hidden sources are applied at
read time too, because a source switched off after the last finder run must
vanish now, not at the next refresh.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import select

from streamselect.core.event_datetime import event_is_on_now
from streamselect.core.games.finder import GUIDE, SportSettings
from streamselect.core.games.models import GameDB, GameFeedDB

UPCOMING, ON_NOW, ENDING, OVER = "upcoming", "on_now", "ending", "over"


@dataclass(frozen=True)
class GameFeedDTO:
    channel_id: Optional[str]
    name: str
    collection: str
    from_guide: bool
    time_from: str = ""          # "zone", "clock", "guide", or "" (joined by its teams alone)


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
    if now < start:
        return UPCOMING
    # The one "is it on" rule (event_datetime), given the sport's lengths as the stop.
    if event_is_on_now(start, start + settings.usual_length, now):
        return ON_NOW
    if event_is_on_now(start, start + settings.long_limit, now):
        return ENDING
    return OVER


def best_feed(game: GameDTO) -> Optional[GameFeedDTO]:
    """The feed a click on the game plays: the first of :attr:`GameDTO.playable`.

    ``load_games`` orders feeds by ``_FEED_RANK``; playback history (smooth or
    stalling) will refine this later.
    """
    feeds = game.playable
    return feeds[0] if feeds else None


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
    feeds: dict[int, list[GameFeedDTO]] = {}
    for f in session.execute(select(GameFeedDB).where(GameFeedDB.game_id.in_([g.id for g in rows]))
                             .order_by(GameFeedDB.id)).scalars():
        if f.source != GUIDE and f.source in hidden_provider_ids:
            continue
        feeds.setdefault(f.game_id, []).append(
            GameFeedDTO(f.channel_id, f.name, f.collection, f.from_guide,
                        "guide" if f.from_guide else f.time_from))
    for gid, fs in feeds.items():
        fs.sort(key=lambda f: _FEED_RANK.get(f.time_from, 2))
        # One feed per channel: a guide programme on a channel already listed by
        # name adds no second place to watch (the named listing ranks first).
        seen: set = set()
        feeds[gid] = [f for f in fs if not f.channel_id or not (f.channel_id in seen or seen.add(f.channel_id))]
    out = []
    for g in rows:
        dto = GameDTO(g.id, g.sport, g.league, g.team_a, g.team_b, g.start_utc, g.level,
                      g.replay, g.collections, tuple(feeds.get(g.id, ())))
        if dto.playable:
            out.append(dto)
    return out
