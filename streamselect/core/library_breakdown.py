"""What the Library breakdown view shows: how sports channels were sorted, and what wasn't.

Design "Library Breakdown" rev 1 (owner accepted BV-Q1-Q13, 2026-11-27). Two
reads, each run off the UI thread through the host's query seam and returning
frozen DTOs: :func:`sports_breakdown` (the Sports tab) and :func:`catch_all`
(the Nothing identified tab), plus :func:`channel_ids` for a clicked name or
count. Everything counts the visible sources only (BV-Q13): a disabled or
expired source is never shown or counted.

Every figure is read from what ingestion and the game finder stored
(``sport_type``, ``sport_from``, ``league_name``, ``sport_teams``); nothing
here classifies a channel again. The catch-all reads the matchup out of each
unidentified name, because "who plays whom" is what it groups by.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, or_, select

from streamselect.core import sports_catalog
from streamselect.core.database import ChannelDB
from streamselect.core.games.identify import fitting_leagues, load_leagues
from streamselect.core.games.models import SportTeamDB
from streamselect.core.repositories.provider import ProviderRepository

#: The special views whose rows carry a sport (special_content).
VIEWS = ("sports", "ppv", "live_event")
#: The kinds' keys in :attr:`SportsBreakdown.kinds`, beside the stored kinds.
SPORT, NONE = "sport", "none"
#: Examples kept per collection in the catch-all.
EXAMPLES = 2


@dataclass(frozen=True)
class SportRow:
    key: str
    name: str
    channels: int
    #: (sport_from, channels), most first.
    decided_by: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class LeagueRow:
    name: str               # "" for the sport's channels with no league
    channels: int
    finder: str             # sports_catalog.FINDER_*, or "" when the list has no such league
    confirmed: int
    unconfirmed: int


@dataclass(frozen=True)
class SportsBreakdown:
    total: int
    #: SPORT / NETWORK / SLOT / UNKNOWN / NONE -> channels.
    kinds: dict
    sports: tuple[SportRow, ...]
    #: sport key -> its leagues, most channels first.
    leagues: dict
    #: "sport/League" -> ((team name, confirmed), ...), confirmed first.
    teams: dict
    #: The sport the view opens on: the first in the Sports view's order that has channels.
    first_sport: str


@dataclass(frozen=True)
class Listing:
    """One unidentified listing: clicking it shows the channel in the details pane."""

    channel_id: str
    name: str


@dataclass(frozen=True)
class CollectionRow:
    collection: str
    games: int
    examples: tuple[Listing, ...]


@dataclass(frozen=True)
class CatchAll:
    total: int
    #: Games two confirmed teams of one league name, not yet tagged (the next finder run tags them).
    named_by_teams: int
    #: (listing, (league names, ...)): two or more leagues fit.
    either: tuple[tuple[Listing, tuple[str, ...]], ...]
    strangers: tuple[CollectionRow, ...]
    strangers_total: int
    not_games: tuple[Listing, ...]


def _visible(session, query):
    hidden = list(ProviderRepository(session).get_hidden_provider_ids())
    query = query.where(ChannelDB.special_view.in_(VIEWS))
    return query.where(ChannelDB.provider_id.not_in(hidden)) if hidden else query


def _sport_order() -> list[str]:
    """The Sports view's order (its finder sports), then the rest of the list."""
    from streamselect.core.games.store import sport_settings
    first = list(sport_settings())
    return first + [s.key for s in sports_catalog.sports() if s.key not in first]


def sports_breakdown(session) -> SportsBreakdown:
    """The Sports tab: kinds, every sport and how it was decided, leagues, teams."""
    rows = session.execute(_visible(session, select(
        ChannelDB.sport_type, ChannelDB.sport_from, ChannelDB.league_name, func.count())
        .group_by(ChannelDB.sport_type, ChannelDB.sport_from, ChannelDB.league_name))).all()
    kinds: Counter = Counter()
    per_sport: dict[str, Counter] = defaultdict(Counter)
    per_league: dict[str, Counter] = defaultdict(Counter)
    for sport, source, league, n in rows:
        if not sport:
            kinds[NONE] += n
        elif sports_catalog.is_kind(sport):
            kinds[sport] += n
        else:
            kinds[SPORT] += n
            per_sport[sport][source or ""] += n
            per_league[sport][league or ""] += n
    teams: dict[str, list[tuple[str, bool]]] = defaultdict(list)
    for key, name, last_in_game in session.execute(
            select(SportTeamDB.league_key, SportTeamDB.name, SportTeamDB.last_in_game)
            .order_by(SportTeamDB.last_in_game.is_(None), SportTeamDB.name)):
        teams[key].append((name, last_in_game is not None))
    finder = {(lg.sport, lg.name): lg.finder for s in sports_catalog.sports() for lg in s.leagues}

    def league_row(sport: str, name: str, n: int) -> LeagueRow:
        book = teams.get(f"{sport}/{name}", [])
        confirmed = sum(1 for _, c in book if c)
        return LeagueRow(name, n, finder.get((sport, name), ""), confirmed, len(book) - confirmed)

    sports = tuple(SportRow(key, sports_catalog.sport_label(key), sum(c.values()), tuple(c.most_common()))
                   for key, c in sorted(per_sport.items(), key=lambda kv: -sum(kv[1].values())))
    leagues = {sport: tuple(league_row(sport, name, n) for name, n in c.most_common())
               for sport, c in per_league.items()}
    first = next((k for k in _sport_order() if k in per_sport), sports[0].key if sports else "")
    return SportsBreakdown(sum(kinds.values()), dict(kinds), sports, leagues,
                           {k: tuple(v) for k, v in teams.items()}, first)


def catch_all(session) -> CatchAll:
    """The Nothing identified tab: the unknown sports rows, grouped by what would fix them."""
    rows = session.execute(_visible(session, select(ChannelDB.id, ChannelDB.name, ChannelDB.category)
                                    .where(ChannelDB.sport_type == sports_catalog.UNKNOWN))).all()
    leagues = load_leagues(session)
    named = 0
    either: list[tuple[Listing, tuple[str, ...]]] = []
    strangers: dict[str, list[Listing]] = defaultdict(list)
    not_games: list[Listing] = []
    for cid, name, collection in rows:
        listing = Listing(cid, name or "")
        fits = fitting_leagues(name, leagues)
        if fits is None:
            not_games.append(listing)
        elif len(fits) == 1:
            named += 1
        elif fits:
            either.append((listing, tuple(lg.name for lg in fits)))
        else:
            strangers[collection or ""].append(listing)
    groups = tuple(CollectionRow(c, len(names), tuple(names[:EXAMPLES]))
                   for c, names in sorted(strangers.items(), key=lambda kv: (-len(kv[1]), kv[0])))
    return CatchAll(len(rows), named, tuple(either), groups,
                    sum(g.games for g in groups), tuple(sorted(not_games, key=lambda li: li.name)))


def channel_ids(session, *, sport: Optional[str] = None, league: Optional[str] = None,
                kind: Optional[str] = None, collection: Optional[str] = None) -> list[str]:
    """The visible channels behind one clicked name or count.

    *sport* (with *league*, "" meaning no league), a *kind* (a stored kind, or
    :data:`SPORT` / :data:`NONE`), or an unidentified *collection*.
    """
    q = _visible(session, select(ChannelDB.id))
    if sport is not None:
        q = q.where(ChannelDB.sport_type == sport)
        if league is not None:
            q = q.where(ChannelDB.league_name == league if league
                        else or_(ChannelDB.league_name.is_(None), ChannelDB.league_name == ""))
    elif kind == NONE:
        q = q.where(ChannelDB.sport_type.is_(None))
    elif kind == SPORT:
        q = q.where(ChannelDB.sport_type.is_not(None), ChannelDB.sport_type.not_in(sports_catalog.KINDS))
    elif kind is not None:
        q = q.where(ChannelDB.sport_type == kind)
    if collection is not None:
        q = q.where(ChannelDB.sport_type == sports_catalog.UNKNOWN,
                    ChannelDB.category == collection if collection
                    else or_(ChannelDB.category.is_(None), ChannelDB.category == ""))
    return list(session.execute(q).scalars())
