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
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Optional

from streamselect.core.event_datetime import zone_label_to_utc
from streamselect.core.games.listing_text import (
    HOME_SECOND, StatedTime, candidate_days, find_date, find_time, league_matcher, matchups,
    matchups_with_separator, norm,
)
from streamselect.core.games import tuning
from streamselect.core.games.teams import Side, TeamBook, team_display

#: The source value a guide (EPG) programme carries instead of a provider id.
GUIDE = "guide"


#: The bundled defaults (``sports_definitions.yaml`` ``sport_defaults.default``): the
#: fallback for a SportSettings built without a sport's own values. Never typed here
#: (owner, 2026-11-18: nothing about the user experience hardcoded).
_D = tuning.settings_kwargs(tuning.defaults())


@dataclass(frozen=True)
class SportSettings:
    """One league's words and its sport's numbers (Settings ▸ Sports; tuning.SPECS
    says what each means). Built by ``store.enabled_leagues`` from the sport's
    defaults and the user's choices; the field defaults are the bundled defaults."""

    sport: str
    league: str
    words: tuple[str, ...]
    #: Two listings of the same pair within this are one game (hockey: one game's
    #: listings spread up to ~70 min: pregame, padded slots).
    same_game: timedelta = _D["same_game"]
    #: A dateless name unchanged on its channel this long is stale (real listings
    #: lived at most ~41 h).
    stale_after: timedelta = _D["stale_after"]
    #: Replays were seen up to ~1.5 days after the game.
    replay_within: timedelta = _D["replay_within"]
    window_back: timedelta = _D["window_back"]
    window_ahead: timedelta = _D["window_ahead"]
    #: A teamless guide programme joins a game only when exactly one game starts this close.
    teamless_guide_within: timedelta = _D["teamless_guide_within"]
    #: A guide-only game this far from the league's usual start times is a replay;
    #: used once that many confirmed games' starts are known, kept that many days.
    usual_hours_off: timedelta = _D["usual_hours_off"]
    usual_hours_min_games: int = _D["usual_hours_min_games"]
    usual_hours_keep_days: int = _D["usual_hours_keep_days"]
    #: Nothing says a game has ended, so "on now" is a length: past usual_length a
    #: game is "likely ending"; past long_limit it is over.
    usual_length: timedelta = _D["usual_length"]
    long_limit: timedelta = _D["long_limit"]
    #: "Not finished — still on" keeps a game on this much longer, offered this
    #: long after its start.
    still_on_adds: timedelta = _D["still_on_adds"]
    still_on_window: timedelta = _D["still_on_window"]
    #: A one-game alert is deleted this long after its game started.
    alert_keep: timedelta = _D["alert_keep"]
    #: "Starting now" may still be sent this long after the start (a late poll).
    start_grace: timedelta = _D["start_grace"]
    #: A play this long or longer counts as watched (shorter = trying a channel).
    watched_after_s: int = _D["watched_after_s"]
    #: A play from this long before a game's start counts as watching it.
    watch_early: timedelta = _D["watch_early"]
    #: Days of viewing behind the "Most watched" order.
    most_watched_days: int = _D["most_watched_days"]
    #: A channel report counts this many days (times the number of reports).
    report_days: int = _D["report_days"]
    #: Minutes of one play of a reported channel that take one report back.
    report_back_min: int = _D["report_back_min"]
    #: A collection's zone-less time agrees with an anchor within this many minutes.
    clock_agree_min: int = _D["clock_agree_min"]
    #: Clock evidence older than this is forgotten.
    clock_keep: timedelta = _D["clock_keep"]


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
    #: play id -> (local day "YYYY-MM-DD", seconds) for plays credited to this league
    #: (:func:`credit_plays`), kept ``SportSettings.most_watched_days``: the league's "most watched"
    #: rank. Kept rather than recomputed so a play stays credited after the teams it
    #: named leave the listings.
    watched: dict[int, tuple[str, int]] = field(default_factory=dict)
    #: starts of this league's confirmed (Level 1) games, kept ``usual_hours_keep_days``:
    #: the times its games usually start (a guide-only game far from them is a replay).
    usual_starts: set[datetime] = field(default_factory=set)




@dataclass(frozen=True)
class PlayIn:
    """One play from the playback log: what the channel was called when it played."""

    id: int
    title: str
    day: str        # the viewer's local day, "YYYY-MM-DD"
    seconds: int


def credit_plays(plays, book: "TeamBook", league: re.Pattern[str]) -> dict[int, tuple[str, int]]:
    """The plays that were this league: the name says the league's word, or a
    matchup in it names two of the league's teams exactly (an NHL game on a channel
    that never says "NHL"). A side the book only half-knows credits nothing."""
    out = {}
    for p in plays:
        u = norm(p.title)
        if league.search(u) or any(book.resolve(a, False)[1] == "exact" and book.resolve(b, False)[1] == "exact"
                                   for a, b in matchups(u, league)):
            out[p.id] = (p.day, p.seconds)
    return out


@dataclass(frozen=True)
class Clock:
    """A collection's learned offset from UTC."""

    source: str
    collection: str
    offset_min: int
    agree: int
    total: int
    #: Set when this collection never showed its own clock and took one learned
    #: elsewhere (:func:`_with_borrowed`): the collection it came from.
    borrowed_from: str = ""

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
    #: The home side's display name when the listings say "away @ / at home" and
    #: none contradicts it; "" when no listing says (owner, 2026-11-14: "at" then).
    home: str = ""

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


def _home(g: dict) -> str:
    """The home side's display name, when the game's listings that say "@" / "at"
    all name the same one; "" when none says or two disagree."""
    homes = set()
    for L in [*g["timed"], *g["extra"]]:
        for p in L.pairs:
            if (p.get("home_second") and len(p["ra"]) == 1 and len(p["rb"]) == 1
                    and frozenset((p["ra"][0], p["rb"][0])) == g["pair"]):
                homes.add(p["rb"][0])
    return team_display(homes.pop()) if len(homes) == 1 else ""


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
        ms = matchups_with_separator(u, league)
        if ms:   # a restatement of the first matchup in shorter words is not a second game
            a0, b0, _ = ms[0]
            ms = [ms[0]] + [(a, b, sep) for a, b, sep in ms[1:]
                            if not ((_shares(a, a0) and _shares(b, b0)) or (_shares(a, b0) and _shares(b, a0)))]
        pairs = []
        for a, b, sep in ms:
            ra, ka = book.resolve(a, li.seeded)
            rb, kb = book.resolve(b, li.seeded)
            pairs.append({"ra": ra, "rb": rb, "ka": ka, "kb": kb, "home_second": sep in HOME_SECOND})
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


def _clock_samples(work: list[_L], anchors, memory: Memory, now: datetime, same_game: timedelta,
                   keep: timedelta = _D["clock_keep"]):
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
        game_key = _title(pk) + "@" + a.isoformat(sep=" ", timespec="minutes")   # a key, not a display
        fresh[(L.src.source, L.src.collection)][game_key] = (int(diff), now)
    merged = {k: dict(v) for k, v in memory.clock_samples.items()}
    for k, games in fresh.items():
        merged.setdefault(k, {}).update(games)
    return {k: {g: v for g, v in games.items() if now - v[1] <= keep}
            for k, games in merged.items()}


def _learn_clocks(samples, agree_min: int = _D["clock_agree_min"]) -> dict[tuple[str, str], Clock]:
    clocks = {}
    for (src, coll), games in samples.items():
        diffs = [d for d, _ in games.values()]
        if not diffs:
            continue

        def pick(step):
            best = None
            for c in range(-720, 841, step):
                score = sum(abs(x - c) <= agree_min for x in diffs)
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


def region_tag(collection: str) -> str:
    """The region a collection name opens with — "CA" for "CA| AHL PPV" — or ""
    when it has none (no "|"), in which case nothing is borrowed for it."""
    return collection.split("|", 1)[0].strip().upper() if "|" in collection else ""


def _with_borrowed(clocks: dict, known, work: list[_L]) -> dict:
    """*clocks* plus a borrowed clock for each collection that states clock times
    but never showed its own clock — nothing typed in, only what was learned.

    A clock belongs to a collection, not a league, so first the same collection's
    clock learned by another league's run (*known*). Failing that, the clock its
    source's sibling collections share: same source, same :func:`region_tag`, and
    every learned sibling on ONE offset ("CA| AHL PPV" takes "CA| SPORTS PPV"'s,
    learned from NHL games; owner, 2026-11-17: "it should have to have a way to
    figure it out internally"). Siblings that disagree, or none, lend nothing,
    and such a listing still gets no time.
    """
    pool = {(c.source, c.collection): c for c in known if c.learned}
    pool.update({k: c for k, c in clocks.items() if c.learned})
    out = dict(clocks)
    wanted = {(L.src.source, L.src.collection) for L in work
              if L.src.source != GUIDE and L.time and not L.time.zone and L.utc is None}
    for src, coll in wanted:
        if (src, coll) in out and out[(src, coll)].learned:
            continue
        same = pool.get((src, coll))
        if same is not None:
            out[(src, coll)] = replace(same, borrowed_from=coll)
            continue
        tag = region_tag(coll)
        siblings = [c for (s, cn), c in pool.items() if s == src and cn != coll and tag
                    and region_tag(cn) == tag]
        if siblings and len({c.offset_min for c in siblings}) == 1:
            first = siblings[0]
            out[(src, coll)] = Clock(src, coll, first.offset_min,
                                     sum(c.agree for c in siblings), sum(c.total for c in siblings),
                                     borrowed_from=", ".join(sorted(c.collection for c in siblings)))
    return out


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
            how = "borrowed" if clock.borrowed_from else "clock"
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


def _split(listings: list[ListingIn], league: re.Pattern[str]) -> tuple[list[ListingIn], list[ListingIn]]:
    """(listings naming the league in their name or collection: the seed, the rest)."""
    seeded, others = [], []
    for li in listings:
        hit = league.search(norm(li.name)) or (li.source != GUIDE and league.search(norm(li.collection)))
        (seeded if hit else others).append(li)
    return seeded, others


def learn_teams(listings: list[ListingIn], settings: SportSettings) -> TeamBook:
    """The league's team book, learned from its seed listings and guide titles.

    :func:`find_games` reads its games against this book; the store keeps the
    book's teams (``sport_teams``), so one run builds it once and passes it in.
    """
    league = league_matcher(settings.words)
    seeded, _ = _split(listings, league)
    return TeamBook((norm(li.name) for li in seeded if li.source != GUIDE),
                    (norm(li.name) for li in seeded if li.source == GUIDE), league)


def find_games(listings: list[ListingIn], settings: SportSettings, now: datetime,
               memory: Optional[Memory] = None,
               known: tuple[Clock, ...] = (), plays=(),
               book: Optional[TeamBook] = None) -> tuple[list[Game], Memory, list[Clock]]:
    """Find one sport's games among *listings*.

    Args:
        listings: every live channel of the active sources, plus the guide
            programmes in the window (``source=GUIDE``, ``guide_utc`` set).
        settings: the sport's league words and measured constants.
        now: UTC-naive; never read from the clock here.
        memory: what the previous run returned (empty on the first run).
        known: clocks other leagues' runs learned; a collection without its own
            borrows from them (:func:`_with_borrowed`).
        plays: recent plays (:class:`PlayIn`); those that were this league join
            ``memory.watched`` (:func:`credit_plays`), which drops days past
            ``settings.most_watched_days``.
        book: the team book :func:`learn_teams` built from these same
            listings; learned here when not given.

    Returns:
        (games in the window and outside it, the memory for the next run, learned clocks)
    """
    memory = memory or Memory()
    league = league_matcher(settings.words)
    seeded, others = _split(listings, league)
    book = book if book is not None else learn_teams(listings, settings)
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
    samples = _clock_samples(work, anchors, memory, now, settings.same_game, settings.clock_keep)
    clocks = _with_borrowed(_learn_clocks(samples, settings.clock_agree_min), known, work)
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
        # Borrowed clocks are an inference (_with_borrowed): two collections that
        # agree only because each borrowed a clock confirm the GAME, not its time,
        # when their times disagree — Cleveland at Hamilton, "8pm" in one and
        # 19:00 in another, an hour apart (2026-11-17). Unconfirmed: less certain.
        borrowed = [L.utc for L in g["timed"] if L.time_from == "borrowed"]
        if (g["level"] == 1 and borrowed and len(borrowed) == len(g["timed"])
                and (max(borrowed) - min(borrowed)).total_seconds() / 60 > settings.clock_agree_min):
            g["level"] = 2
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

    # Usual start times (owner, 2026-11-19): a game only the guide lists, starting far
    # from when this league's confirmed games start, is a rerun — Eurosport's
    # morning-after NBA games were read as games that morning.
    usual = {u for u in memory.usual_starts if now - u <= timedelta(days=settings.usual_hours_keep_days)}
    usual |= {g["utc"] for g in G if g["level"] == 1}
    if len(usual) >= settings.usual_hours_min_games:
        usual_min = [u.hour * 60 + u.minute for u in usual]
        off = settings.usual_hours_off.total_seconds() / 60
        for g in G:
            if g["level"] != 2 or not all(L.src.source == GUIDE for L in g["timed"]):
                continue
            m = g["utc"].hour * 60 + g["utc"].minute
            if min(min(abs(m - x), 1440 - abs(m - x)) for x in usual_min) > off:
                g["level"], g["replay"] = 3, True

    # Team clash (owner, 2026-11-19): a team plays one game at a time. Of two games
    # sharing a team and overlapping, the one with more evidence stands (confirmed,
    # more collections, earlier); the other is a replay or a leftover listing.
    kept: list[dict] = []
    for g in sorted((g for g in G if g["level"] in (1, 2)), key=lambda g: (g["level"], -g["colls"], g["utc"])):
        if any(g["pair"] & k["pair"] and abs(g["utc"] - k["utc"]) < settings.usual_length for k in kept):
            g["level"], g["replay"] = 3, True
        else:
            kept.append(g)

    # Teamless guide programmes: a feed, never evidence, when exactly one game starts close by.
    for L in work:
        if L.src.source != GUIDE or L.kind != "nomatchup" or L.utc is None or not L.src.channel_id:
            continue
        # A programme dated another day (a magazine show, "Basket Room … 16/11/2026")
        # is not this game, whatever it is near.
        stated = find_date(norm(L.src.name), L.utc)
        if stated is not None and abs(stated.date() - L.utc.date()) > timedelta(days=1):
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
        games.append(Game(settings.sport, settings.league, a, b, g["utc"], g["level"], g["replay"], g["colls"],
                          feeds, home=_home(g)))

    confirmed = {k: {u for u in v if now - u <= settings.replay_within} for k, v in memory.confirmed.items()}
    for g in games:
        # A past game behind the listing window that two collections agree on is
        # remembered too, so the replay rule has the original even on a league's
        # first run (owner, 2026-11-19: "seed memory on first run").
        if g.level == 1 or (g.level == 4 and g.collections >= 2 and g.start_utc < lo):
            confirmed.setdefault(g.title, set()).add(g.start_utc)
    current = {(L.src.channel_id, L.src.name) for L in work}
    first_seen = {k: v for k, v in first_seen.items() if k in current}
    oldest = (now - timedelta(days=settings.most_watched_days)).date().isoformat()
    watched = {pid: v for pid, v in {**memory.watched, **credit_plays(plays, book, league)}.items()
               if v[0] >= oldest}
    usual_out = {u for u in usual if now - u <= timedelta(days=settings.usual_hours_keep_days)}
    return games, Memory(samples, first_seen, confirmed, watched, usual_out), list(clocks.values())
