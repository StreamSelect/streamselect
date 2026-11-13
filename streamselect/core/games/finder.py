"""Turn one sport's listings into games: two sides, one start, every feed that shows it.

Pure: listings and the memory of earlier runs go in, games and the updated
memory come out. No database, no clock read (``now`` is passed in), no source,
collection or channel name in any rule. The method, its evidence and its
constants are written up in the "Finding live games" method document; each
constant below names the observation it came from.

The confidence ladder:

* Level 1 — two or more independent collections agree on both sides and the
  start (the guide counts once, however many guide channels show it).
* Level 2 — one collection.
* Level 3 — a replay of a game already played.
* Level 4 — outside the window (old, or far ahead).
"""

from __future__ import annotations

import collections
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from streamselect.core.event_datetime import zone_label_to_utc
from streamselect.core.games.listing_text import (
    StatedTime, candidate_days, find_date, find_time, league_matcher, matchups, norm,
)
from streamselect.core.games.teams import Side, TeamBook, team_display

#: The source value a guide (EPG) programme carries instead of a provider id.
GUIDE = "guide"


@dataclass(frozen=True)
class SportSettings:
    """The few per-sport numbers; everything else is shared by every sport."""

    sport: str
    league: str
    words: tuple[str, ...]
    #: Two listings of the same pair within this are one game. Hockey: listings
    #: of one game spread up to ~70 min (pregame, padded slots).
    same_game: timedelta = timedelta(minutes=90)
    #: A dateless name unchanged on its channel this long is stale. Real game
    #: listings lived at most ~41 h (up ~25 h ahead, gone ~16 h after).
    stale_after: timedelta = timedelta(hours=48)
    #: Replays were seen up to ~1.5 days after the game.
    replay_within: timedelta = timedelta(hours=72)
    window_back: timedelta = timedelta(hours=18)
    window_ahead: timedelta = timedelta(hours=36)
    #: A teamless guide programme joins a game only when exactly one game starts this close.
    teamless_guide_within: timedelta = timedelta(minutes=15)


#: A collection's zone-less time agrees with an anchor within this many minutes
#: (listings often carry the pregame or a padded start).
CLOCK_AGREE_MIN = 40
#: Clock evidence older than this is forgotten.
CLOCK_KEEP = timedelta(days=14)


@dataclass(frozen=True)
class ListingIn:
    """One channel, or one guide programme, that may show a game."""

    source: str                 # provider id, or GUIDE
    collection: str             # the channel's category, or the guide channel's name
    name: str                   # channel name, or programme title
    channel_id: Optional[str] = None
    guide_utc: Optional[datetime] = None   # a guide programme's start, UTC
    seeded: bool = False        # names the league itself (set by find_games)


@dataclass
class Memory:
    """What one run hands the next. All times UTC-naive."""

    #: (source, collection) -> {game key: (minutes off the anchor, when seen)}
    clock_samples: dict[tuple[str, str], dict[str, tuple[int, datetime]]] = field(default_factory=dict)
    #: (channel id, name) -> first time that name was seen on that channel
    first_seen: dict[tuple[str, str], datetime] = field(default_factory=dict)
    #: game title -> starts of earlier Level 1 games with those teams
    confirmed: dict[str, set[datetime]] = field(default_factory=dict)


@dataclass(frozen=True)
class Clock:
    """A collection's learned offset from UTC."""

    source: str
    collection: str
    offset_min: int
    agree: int
    total: int

    @property
    def learned(self) -> bool:
        return self.agree >= 2 and self.agree / self.total >= 0.75


@dataclass(frozen=True)
class GameFeed:
    """One listing of a game."""

    source: str
    collection: str
    name: str
    channel_id: Optional[str]
    from_guide: bool
    #: How the start was read: "zone", "clock", "guide", or "" when the listing
    #: joined by its teams alone (no usable time) or as a teamless guide programme.
    time_from: str
    start_utc: Optional[datetime]
    counts: bool                # counted toward the level (a teamless guide feed is not)


@dataclass(frozen=True)
class Game:
    sport: str
    league: str
    team_a: str                 # display names, alphabetical
    team_b: str
    start_utc: datetime
    level: int
    replay: bool
    collections: int
    feeds: tuple[GameFeed, ...]

    @property
    def title(self) -> str:
        return f"{self.team_a} vs {self.team_b}"


@dataclass
class _L:
    """A listing being worked on."""

    src: ListingIn
    u: str
    pairs: list[dict]
    date: Optional[datetime]
    time: Optional[StatedTime]
    utc: Optional[datetime] = None
    time_from: str = ""
    kind: str = ""
    stale: bool = False
    in_game: bool = False


def _title(pair: frozenset) -> str:
    return " vs ".join(sorted(team_display(t) for t in pair))


def _pair_key(L: _L) -> Optional[frozenset]:
    if not L.pairs:
        return None
    p = L.pairs[0]
    if len(p["ra"]) == 1 and len(p["rb"]) == 1 and p["ra"][0] != p["rb"][0]:
        return frozenset((p["ra"][0], p["rb"][0]))
    return None


def _coll_key(L: _L) -> tuple:
    return (GUIDE,) if L.src.source == GUIDE else (L.src.source, L.src.collection)


def _shares(x: Side, y: Side) -> bool:
    return any(len(w) >= 3 and w in y for w in x)


def _read(listings: list[ListingIn], book: TeamBook, league, now: datetime) -> list[_L]:
    out = []
    for li in listings:
        u = norm(li.name)
        ms = matchups(u, league)
        if ms:   # a restatement of the first matchup in shorter words is not a second game
            a0, b0 = ms[0]
            ms = [ms[0]] + [(a, b) for a, b in ms[1:]
                            if not ((_shares(a, a0) and _shares(b, b0)) or (_shares(a, b0) and _shares(b, a0)))]
        pairs = []
        for a, b in ms:
            ra, ka = book.resolve(a, li.seeded)
            rb, kb = book.resolve(b, li.seeded)
            pairs.append({"ra": ra, "rb": rb, "ka": ka, "kb": kb})
        L = _L(li, u, pairs, find_date(u, now), find_time(u))
        if li.guide_utc is not None:
            L.utc, L.time_from = li.guide_utc, "guide"
        resolved = [p for p in pairs if p["ra"] and p["rb"]]
        if len({frozenset((tuple(p["ra"]), tuple(p["rb"]))) for p in resolved}) >= 2:
            L.kind = "multi"
        elif resolved and "unknown" not in (resolved[0]["ka"], resolved[0]["kb"]):
            L.kind = "game"
        elif pairs:
            L.kind = "partial"
        else:
            L.kind = "nomatchup"
        out.append(L)
    return out


def _anchor_times(work: list[_L]) -> dict[frozenset, list[datetime]]:
    anchors: dict[frozenset, list[datetime]] = collections.defaultdict(list)
    for L in work:
        pk = _pair_key(L) if L.kind == "game" else None
        if not pk:
            continue
        if L.utc is None and L.time and L.time.zone and L.date:
            u = zone_label_to_utc(L.date.replace(hour=L.time.hour, minute=L.time.minute), L.time.zone)
            if u is not None:
                L.utc, L.time_from = u, "zone"
        if L.utc is not None:
            anchors[pk].append(L.utc)
    return anchors


def _clock_samples(work: list[_L], anchors, memory: Memory, now: datetime, same_game: timedelta):
    fresh: dict[tuple[str, str], dict[str, tuple[int, datetime]]] = collections.defaultdict(dict)
    for L in work:
        pk = _pair_key(L)
        if L.kind != "game" or L.utc is not None or not L.time or not pk or not anchors.get(pk):
            continue
        h, m = L.time.hour, L.time.minute
        ref = L.date.replace(hour=h, minute=m) if L.date else now
        nearest = min(anchors[pk], key=lambda a: abs(ref - a))
        group = sorted(x for x in anchors[pk] if abs(x - nearest) <= same_game)
        a = group[len(group) // 2]   # the middle of that game's stated times
        if L.date:
            diff = (L.date.replace(hour=h, minute=m) - a).total_seconds() / 60
            if abs(diff) > 14 * 60:
                continue
        else:
            diff = ((h * 60 + m) - (a.hour * 60 + a.minute)) % 1440
            diff = diff - 1440 if diff >= 720 else diff
        game_key = _title(pk) + "@" + a.strftime("%Y-%m-%d %H:%M")
        fresh[(L.src.source, L.src.collection)][game_key] = (int(diff), now)
    merged = {k: dict(v) for k, v in memory.clock_samples.items()}
    for k, games in fresh.items():
        merged.setdefault(k, {}).update(games)
    return {k: {g: v for g, v in games.items() if now - v[1] <= CLOCK_KEEP}
            for k, games in merged.items()}


def _learn_clocks(samples) -> dict[tuple[str, str], Clock]:
    clocks = {}
    for (src, coll), games in samples.items():
        diffs = [d for d, _ in games.values()]
        if not diffs:
            continue

        def pick(step):
            best = None
            for c in range(-720, 841, step):
                score = sum(abs(x - c) <= CLOCK_AGREE_MIN for x in diffs)
                key = (score, -sum(abs(x - c) for x in diffs))
                if best is None or key > best[0]:
                    best = (key, c, score)
            return best[1], best[2]

        c, n = pick(60)                        # whole hours first
        if not (n >= 2 and n / len(diffs) >= 0.75):
            c2, n2 = pick(30)                  # half hours only if no whole hour fits
            if n2 > n:
                c, n = c2, n2
        clocks[(src, coll)] = Clock(src, coll, c, n, len(diffs))
    return clocks


def _place_times(work: list[_L], anchors, clocks, now: datetime) -> None:
    for L in work:
        if L.utc is not None or not L.time:
            continue
        h, m, zone = L.time
        clock = clocks.get((L.src.source, L.src.collection))
        if zone and not L.date:
            cands = [u for d in candidate_days(now, h, m) if (u := zone_label_to_utc(d, zone))]
            how = "zone"
        elif clock and clock.learned:
            off = timedelta(minutes=clock.offset_min)
            if L.date:
                cands = [L.date.replace(hour=h, minute=m) - off]
            else:
                cands = [d - off for d in candidate_days(now, h, m)]
            how = "clock"
        else:
            continue
        if not cands:
            continue
        pk = _pair_key(L)
        target = min(anchors[pk], key=lambda a: abs(a - now)) if pk and anchors.get(pk) else now
        L.utc, L.time_from = min(cands, key=lambda x: abs(x - target)), how


def _mark_stale(work: list[_L], memory: Memory, now: datetime, stale_after: timedelta) -> dict:
    first_seen = dict(memory.first_seen)
    for L in work:
        cid = L.src.channel_id
        if not cid or L.src.source == GUIDE:
            continue
        key = (cid, L.src.name)
        first = first_seen.setdefault(key, now)
        if L.time and L.date is None and now - first >= stale_after:
            L.stale = True
    return first_seen


def find_games(listings: list[ListingIn], settings: SportSettings, now: datetime,
               memory: Optional[Memory] = None) -> tuple[list[Game], Memory, list[Clock]]:
    """Find one sport's games among *listings*.

    Args:
        listings: every live channel of the active sources, plus the guide
            programmes in the window (``source=GUIDE``, ``guide_utc`` set).
        settings: the sport's league words and measured constants.
        now: UTC-naive; never read from the clock here.
        memory: what the previous run returned (empty on the first run).

    Returns:
        (games in the window and outside it, the memory for the next run, learned clocks)
    """
    memory = memory or Memory()
    league = league_matcher(settings.words)
    seeded, others = [], []
    for li in listings:
        hit = league.search(norm(li.name)) or (li.source != GUIDE and league.search(norm(li.collection)))
        (seeded if hit else others).append(li)
    book = TeamBook((norm(li.name) for li in seeded if li.source != GUIDE),
                    (norm(li.name) for li in seeded if li.source == GUIDE), league)
    seeded = [ListingIn(**{**li.__dict__, "seeded": True}) for li in seeded]
    # Past the seed: only channels whose BOTH sides are exactly known teams.
    widened = []
    for li in others:
        if li.source == GUIDE:
            continue
        ms = matchups(norm(li.name), league)
        if any(book.resolve(a, False)[1] == "exact" and book.resolve(b, False)[1] == "exact" for a, b in ms):
            widened.append(li)
    work = _read(seeded + widened, book, league, now)

    anchors = _anchor_times(work)
    samples = _clock_samples(work, anchors, memory, now, settings.same_game)
    clocks = _learn_clocks(samples)
    _place_times(work, anchors, clocks, now)
    first_seen = _mark_stale(work, memory, now, settings.stale_after)

    # Group: same pair, starts within same_game, at least one seed listing.
    by_pair: dict[frozenset, list[_L]] = collections.defaultdict(list)
    for L in work:
        pk = _pair_key(L)
        if L.kind == "game" and pk and L.utc is not None and not L.stale:
            by_pair[pk].append(L)
    groups: list[tuple[frozenset, list[_L]]] = []
    for pk, Ls in by_pair.items():
        Ls.sort(key=lambda x: x.utc)
        cur: list[_L] = []
        for L in Ls:
            if cur and L.utc - cur[-1].utc > settings.same_game:
                groups.append((pk, cur))
                cur = []
            cur.append(L)
        groups.append((pk, cur))
    groups = [(pk, Ls) for pk, Ls in groups if any(L.src.seeded for L in Ls)]

    lo, hi = now - settings.window_back, now + settings.window_ahead
    G = []
    for pk, Ls in groups:
        start = sorted(L.utc for L in Ls)[len(Ls) // 2]
        G.append({"pair": pk, "utc": start, "timed": list(Ls), "extra": [], "inwin": lo <= start <= hi})
        for L in Ls:
            L.in_game = True

    # A listing whose side could mean two teams, or with no usable time, joins
    # only when exactly one in-window game fits it.
    for L in work:
        if L.in_game or not L.pairs:
            continue
        if L.kind == "partial":
            p = L.pairs[0]
            if "unknown" in (p["ka"], p["kb"]):
                continue
            cands = {frozenset((x, y)) for x in p["ra"] for y in p["rb"] if x != y}
        elif L.kind == "game" and L.utc is None and _pair_key(L):
            cands = {_pair_key(L)}
        else:
            continue
        fits = [g for g in G if g["pair"] in cands and g["inwin"]
                and (L.utc is None or abs(g["utc"] - L.utc) <= settings.same_game)]
        if len(fits) == 1:
            (fits[0]["timed"] if L.utc is not None else fits[0]["extra"]).append(L)
            L.in_game = True

    # Levels.
    for g in G:
        g["colls"] = len({_coll_key(L) for L in g["timed"]})
        g["level"] = 4 if not g["inwin"] else (1 if g["colls"] >= 2 else 2)
        g["replay"] = False
    airings: dict[tuple, set[datetime]] = collections.defaultdict(set)
    for g in G:
        for L in g["timed"]:
            if L.src.source == GUIDE:
                airings[(L.src.collection, g["pair"])].add(g["utc"])
    for g in G:
        if g["level"] != 2:
            continue
        lo_r, hi_r = g["utc"] - settings.replay_within, g["utc"] - settings.same_game
        earlier = [h["utc"] for h in G if h["pair"] == g["pair"] and h["colls"] >= 2 and lo_r <= h["utc"] < hi_r]
        earlier += [u for u in memory.confirmed.get(_title(g["pair"]), ()) if lo_r <= u < hi_r]
        for L in g["timed"]:   # a game is played live once: the same guide channel again is a replay
            if L.src.source == GUIDE:
                earlier += [u for u in airings[(L.src.collection, g["pair"])] if lo_r <= u < hi_r]
        if earlier:
            g["level"], g["replay"] = 3, True

    # Teamless guide programmes: a feed, never evidence, when exactly one game starts close by.
    for L in work:
        if L.src.source != GUIDE or L.kind != "nomatchup" or L.utc is None or not L.src.channel_id:
            continue
        near = [g for g in G if g["level"] in (1, 2) and abs(g["utc"] - L.utc) <= settings.teamless_guide_within]
        if len(near) == 1:
            near[0]["extra"].append(L)

    games = []
    for g in G:
        feeds = tuple(
            GameFeed(L.src.source, L.src.collection, L.src.name, L.src.channel_id,
                     L.src.source == GUIDE, L.time_from if L.utc is not None else "",
                     L.utc, L in g["timed"])
            for L in [*g["timed"], *g["extra"]])
        a, b = sorted(team_display(t) for t in g["pair"])
        games.append(Game(settings.sport, settings.league, a, b, g["utc"], g["level"], g["replay"], g["colls"], feeds))

    confirmed = {k: {u for u in v if now - u <= settings.replay_within} for k, v in memory.confirmed.items()}
    for g in games:
        if g.level == 1:
            confirmed.setdefault(g.title, set()).add(g.start_utc)
    current = {(L.src.channel_id, L.src.name) for L in work}
    first_seen = {k: v for k, v in first_seen.items() if k in current}
    return games, Memory(samples, first_seen, confirmed), list(clocks.values())
