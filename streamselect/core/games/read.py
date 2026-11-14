"""Reading stored games for a screen: frozen DTOs, the game's state now, its best feed.

Screens never parse a channel name for a game: everything here reads what
:mod:`streamselect.core.games.store` wrote. Hidden sources are applied at
read time too, because a source switched off after the last finder run must
vanish now, not at the next refresh.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import case, func, select

from streamselect.core.category_headings import split_head
from streamselect.core.database import ChannelDB
from streamselect.core.event_datetime import DEFAULT_EVENT_DURATION, event_is_on_now
from streamselect.core.games.finder import SportSettings
from streamselect.core.games.models import GameDB, GameEndDB, GameFeedDB
from streamselect.core.playback_models import PlaybackEventDB
from streamselect.core.quality_vocab import QUALITY_TIER_RANK
from streamselect.core.region_codes import (
    AUDIO_LANG_WORD_MAP, ISO_639_1_LANGUAGE_NAMES, PLATFORM_CODES, REGION_FULL_NAMES, leading_country,
)
from streamselect.core.repositories.stream_info import StreamInfoRepository
from streamselect.core.stream_info import measured_quality, summarize

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
    #: Set when the user reported this channel's collection (SV-Q37-Q39): the text
    #: its row's report icon explains itself with. Empty when not reported.
    report: str = ""
    #: The report kinds active on it for this game (DIDNT_PLAY / WRONG_CONTENT): what
    #: the right-click menus tick.
    reported: tuple = ()
    #: ``quality`` was measured by the app itself (played or probed), not read
    #: off the name: the chip carries the measured mark (PLAYED-3).
    verified: bool = False
    #: The row as designed in The Sports Desk rev 8 (SV-Q68-Q80), all from stored
    #: fields: the channel's own cleaned name (``detected_title``), its package
    #: name cleaned at ingestion (``detected_collection``) and the quality words
    #: peeled off it (``detected_collection_quality``), and what playing it measured.
    own_name: str = ""
    package: str = ""
    package_quality: tuple = ()
    language: str = ""          # measured audio language, two letters ("EN"); "" when not measured
    fps: str = ""               # measured frame rate ("30fps"); "" when not measured
    #: A muted note telling two otherwise identical rows apart (SV-Q79), set by load_games.
    detail: str = ""

    @property
    def collection_key(self) -> str:
        """``"<source>|<collection>"`` — what a preference or a hide sticks to: slot
        channel ids change between refreshes, the collection does not."""
        return f"{self.provider_id}|{self.channel_collection}"

    @property
    def station(self) -> str:
        """The package without its region head: "US| ESPN+ PPV VIP" -> "ESPN+ PPV VIP",
        "SWEDEN TELIA PLAY" -> "TELIA PLAY" (category_headings / region_codes)."""
        # NFKC folds the superscript letters some collections use ("NORWAY ᴳᴼᴸᴰ ᴿᴬᵂ"),
        # which otherwise render tiny — the same folding the finder reads names with.
        c = unicodedata.normalize("NFKC", self.package or self.channel_collection or self.collection)
        return split_head(c)[1] or (leading_country(c) or ("", c))[1] or c

    @property
    def title(self) -> str:
        """What the row is called (SV-Q77/Q80): a regular channel found through the
        guide by its own name; an event channel by its package; a package that is
        only a country or language name ("DE| GERMANY") by the country."""
        if self.from_guide and self.own_name:
            return self.own_name
        if _only_place_or_language(self.station):
            return REGION_FULL_NAMES.get(self.region, self.station)
        return self.station

    @property
    def tier(self) -> str:
        """One resolution tier: the measured one, else the best the name or package claims."""
        if self.verified:
            return self.quality
        claims = [q for q in (self.quality, *self.package_quality) if q in QUALITY_TIER_RANK]
        return max(claims, key=lambda q: QUALITY_TIER_RANK[q], default="")

    @property
    def codecs(self) -> tuple[str, ...]:
        """The quality words that aren't a tier (HEVC, RAW…), each once (SV-Q69)."""
        words = (self.quality, *self.package_quality) if not self.verified else self.package_quality
        return tuple(dict.fromkeys(q for q in words if q and q not in QUALITY_TIER_RANK))


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
    #: The home side when the listings say "away @ / at home", else "".
    home: str = ""
    #: The league's own logo URL, as one of its channels carries it (SV-Q67), else "".
    league_logo: str = ""

    @property
    def league_key(self) -> str:
        """``"hockey/NHL"`` — the key preferences and hides are kept under."""
        return f"{self.sport}/{self.league}"

    @property
    def title(self) -> str:
        """The game's identity: alphabetical, "vs" — what alerts and reports key on."""
        return f"{self.team_a} vs {self.team_b}"

    @property
    def sides(self) -> tuple[str, str, str]:
        """(first, joiner, second) as shown: "away at home" when a listing says so
        (owner, 2026-11-14), else the alphabetical pair joined by "vs"."""
        if self.home in (self.team_a, self.team_b):
            away = self.team_b if self.home == self.team_a else self.team_a
            return away, "at", self.home
        return self.team_a, "vs", self.team_b

    @property
    def matchup(self) -> str:
        """The one-line display title: "Seattle Kraken at Carolina Hurricanes"."""
        return " ".join(self.sides)

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


def event_is_live(game: GameDTO, now: datetime, settings: SportSettings) -> bool:
    """On now or likely ending — what a sport header counts as live."""
    return game_state(game, now, settings) in (ON_NOW, ENDING)


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


#: Channel reports (SV-Q37-Q39), shown as "Nothing showing" and "Not this game"
#: (owner, 2026-11-13); the stored kinds keep their first names.
DIDNT_PLAY, WRONG_CONTENT = "didnt_play", "wrong_content"
_REPORT_WORDS = {DIDNT_PLAY: "nothing showing", WRONG_CONTENT: "not this game"}
#: Where reports live in ``Config.game_channel_prefs[league]``: keyed by CHANNEL id
#: (owner, 2026-11-13: "No picture should be specific to a channel/stream not to a
#: package" — one dead slot in a package of fifteen). Each entry keeps its collection
#: too, so reports can be added up per collection later (analytics). The first
#: collection-keyed store, ``"reports"``, is kept as written and no longer read.
CHANNEL_REPORTS = "channel_reports"
#: A report counts this long after the latest one, times the number of reports
#: (owner, SV-Q38: 30 days to start; more reports extend the tracking).
REPORT_DAYS = 30


def game_key(game: GameDTO) -> str:
    """The game a "not this game" report names: league, teams and start."""
    return f"{game.league_key}|{game.team_a}|{game.team_b}|{game.start_utc.isoformat()}"


def active_reports(reports: list[dict], game: GameDTO, last_watched: Optional[datetime],
                   now: datetime) -> tuple[tuple[str, ...], int]:
    """The report kinds that count on one collection for one game, and how many
    reports stand behind them; ``((), 0)`` when none does (rules: ``report_text``)."""
    relevant = [r for r in reports if r.get("kind") == DIDNT_PLAY
                or (r.get("kind") == WRONG_CONTENT and r.get("game") == game_key(game))]
    if not relevant:
        return (), 0
    latest = max(datetime.fromisoformat(r["at"]) for r in relevant)
    n = len(relevant) - (1 if last_watched is not None and last_watched > latest else 0)
    if n <= 0 or now > latest + timedelta(days=REPORT_DAYS * n):
        return (), 0
    return tuple(sorted({r.get("kind") for r in relevant})), n


def report_text(reports: list[dict], game: GameDTO, last_watched: Optional[datetime],
                now: datetime) -> str:
    """The active report on one collection for one game, as its icon's tooltip; "" if none.

    ``reports``: the stored list for the channel, each ``{"kind", "at", "game"?, ...}``.
    A real watch (``last_watched``, plays of a minute or more) after the latest
    report cancels one report — a feed that came back earns its place back. A
    "not this game" report counts for its own game; "nothing showing" for every game.
    """
    active, n = active_reports(reports, game, last_watched, now)
    if not active:
        return ""
    kinds = [_REPORT_WORDS.get(k, k) for k in active]
    times = "once" if n == 1 else f"{n} times"
    return f"Reported {times} in {game.league} games: {', '.join(kinds)}. Listed last."


def arrange_feeds(game: GameDTO, prefs: dict, history: WatchHistory,
                  now: Optional[datetime] = None) -> GameDTO:
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

    reports = prefs.get(CHANNEL_REPORTS) or {}
    if now is not None and reports:
        def reported(f: GameFeedDTO) -> GameFeedDTO:
            mine, watched = reports.get(f.channel_id, []), history.get(channel_history_key(f.channel_id), (None,))[0]
            return replace(f, report=report_text(mine, game, watched, now),
                           reported=active_reports(mine, game, watched, now)[0])
        keep = [reported(f) if f.channel_id in reports else f for f in keep]

    def key(f: GameFeedDTO):
        _last, secs, plays = history.get(f.collection_key, (None, 0, 0))
        # A reported channel goes last whatever else it has going for it (SV-Q39).
        return (bool(f.report), f.collection_key != preferred, f.collection_key != last, -secs, -plays,
                _FEED_RANK.get(f.time_from, 2))
    return replace(game, feeds=tuple(sorted(keep, key=key)), hidden=tuple(gone))


def mark_finished(session, game: GameDTO, ended_at: datetime) -> None:
    """Record that *game* is over, as of *ended_at* (UTC). Idempotent: a second mark moves the time."""
    session.merge(GameEndDB(league_key=game.league_key, team_a=game.team_a, team_b=game.team_b,
                            start_utc=game.start_utc, ended_at=ended_at))


def channel_history_key(channel_id: Optional[str]) -> str:
    """One channel's own entry in a ``WatchHistory`` (beside the collection entries):
    a real watch of THIS channel takes back one of its reports."""
    return f"channel:{channel_id}"


def load_watch_history(session) -> WatchHistory:
    """Plays that showed a picture, grouped by the played channel's source and collection,
    and per channel under ``channel_history_key``.

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
    history = {f"{pid}|{cat or ''}": (last, int(secs), int(n)) for pid, cat, last, secs, n in rows}
    per_channel = session.execute(
        select(PlaybackEventDB.channel_id,
               func.max(case((watched, PlaybackEventDB.started_at), else_=None)),
               func.coalesce(func.sum(func.min(PlaybackEventDB.seconds_watched, _PLAY_CAP_S)), 0),
               func.count())
        .where(PlaybackEventDB.outcome.in_(("started", "dropped")))
        .group_by(PlaybackEventDB.channel_id)).all()
    history.update({channel_history_key(cid): (last, int(secs), int(n)) for cid, last, secs, n in per_channel})
    return history


#: Two letters for a language name ("English" -> "EN"), from the shared ISO table.
_LANGUAGE_CODE = {name: code.upper() for code, name in ISO_639_1_LANGUAGE_NAMES.items()}
#: Country names (not the streaming platforms that share the table) and language names.
_PLACE_OR_LANGUAGE = ({n.upper() for c, n in REGION_FULL_NAMES.items()
                       if c not in PLATFORM_CODES and n.upper() != c.upper()}
                      | {n.upper() for n in ISO_639_1_LANGUAGE_NAMES.values()})


def _language_words(code: str) -> set[str]:
    """Every way a name spells the row's language chip ("EN" -> EN, ENG, ENGLISH):
    a note never repeats what the chip says (owner, 2026-11-14)."""
    if not code:
        return set()
    name = ISO_639_1_LANGUAGE_NAMES.get(code.lower(), "")
    return {code, *(w for w, n in AUDIO_LANG_WORD_MAP.items() if n == name)}


def _only_place_or_language(name: str) -> bool:
    return name.strip().upper() in _PLACE_OR_LANGUAGE


def _measured_language(seen: dict) -> str:
    """The first measured audio language as two letters ("EN"), else ""."""
    for name in seen.get("audio") or ():
        return _LANGUAGE_CODE.get(name, "")
    return ""


def _measured_fps(record: Optional[dict]) -> str:
    fps = (((record or {}).get("info") or {}).get("video") or {}).get("fps")
    return f"{round(fps)}fps" if isinstance(fps, (int, float)) and fps > 0 else ""


#: Words never worth showing as a look-alike note: times, dates, and words that
#: only say "live" or which sport.
_NOTE_NOISE = frozenset({"LIVE", "VS", "AT", "MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN",
                         "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT",
                         "NOV", "DEC", "AM", "PM", "CET", "CEST", "ET", "PT", "GMT", "UTC"})


def _note_words(name: str, said: set[str]) -> list[str]:
    return [w for w in re.sub(r"[|:@()\-,]", " ", name).split()
            if w.upper() not in _NOTE_NOISE and w.upper() not in said
            and not re.fullmatch(r"[\d.:]+(PM|AM)?", w.upper())]


def look_alike_details(feeds: list[GameFeedDTO]) -> list[GameFeedDTO]:
    """Rows that read the same (title, region and language) get a short note from
    the words of each channel's own name the others lack (SV-Q79): never a word a
    chip already shows, never a time or date; "#1", "#2"… when nothing differs."""
    groups: dict[tuple, list[int]] = {}
    for i, f in enumerate(feeds):
        groups.setdefault((f.title, f.region, f.language), []).append(i)
    out = list(feeds)
    for idx in groups.values():
        if len(idx) < 2:
            continue
        said = [{*QUALITY_TIER_RANK, *feeds[i].codecs, *_language_words(feeds[i].language)} for i in idx]
        words = [_note_words(feeds[i].own_name or feeds[i].name, said[k]) for k, i in enumerate(idx)]
        for k, i in enumerate(idx):
            others = {w.upper() for j, ws in enumerate(words) if j != k for w in ws}
            own = [w for w in words[k] if w.upper() not in others]
            out[i] = replace(feeds[i], detail=" ".join(own[:4]) or f"#{k + 1}")
    return out


def _league_logos(games, feed_rows, logos: dict[str, str]) -> dict[str, str]:
    """league -> its own logo URL: a channel logo whose file is named for the league
    ("…/NHL.png"). Most channel logos are a network's (ESPN, Viaplay), never used as
    the league's mark. Found on any of its games, it serves them all (owner, SV-Q67)."""
    league_of = {g.id: g.league for g in games}
    found: dict[str, str] = {}
    for f in feed_rows:
        url, league = logos.get(f.channel_id), league_of.get(f.game_id)
        if url and league and league not in found:
            stem = url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            if stem.casefold() == league.casefold():
                found[league] = url
    return found


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
    chan, logos, stored = {}, {}, {}
    for cid, pid, cat, region, quality, logo, title, package, pkg_quality in session.execute(
            select(ChannelDB.id, ChannelDB.provider_id, ChannelDB.category,
                   ChannelDB.detected_region, ChannelDB.detected_quality, ChannelDB.logo_url,
                   ChannelDB.detected_title, ChannelDB.detected_collection,
                   ChannelDB.detected_collection_quality)
            .where(ChannelDB.id.in_({f.channel_id for f in feed_rows if f.channel_id}))):
        chan[cid] = (pid, cat, region, quality)
        stored[cid] = (title or "", package or "", tuple((pkg_quality or "").split()))
        if logo and pid not in hidden_provider_ids:
            logos[cid] = logo
    # What the stream itself measured outranks the name's claim, as in the details
    # pane's Versions (PLAYED-3): a played 1080p channel reads FHD, with the mark.
    measured = StreamInfoRepository(session).get_many(list(chan))
    feeds: dict[int, list[GameFeedDTO]] = {}
    for f in feed_rows:
        pid, cat, region, quality = chan.get(f.channel_id, (f.source, f.collection, "", ""))
        if pid in hidden_provider_ids:
            continue
        record = measured.get(f.channel_id)
        seen = summarize(record)
        ours = bool(seen) and seen["source"] in ("played", "probe")
        tier = measured_quality((seen or {}).get("height"))
        own_name, package, package_quality = stored.get(f.channel_id, ("", "", ()))
        feeds.setdefault(f.game_id, []).append(
            GameFeedDTO(f.channel_id, f.name, f.collection, f.from_guide,
                        "guide" if f.from_guide else f.time_from,
                        pid or "", cat or "", region or "", tier or quality or "",
                        verified=bool(tier) and ours, own_name=own_name, package=package,
                        package_quality=package_quality,
                        language=_measured_language(seen) if ours else "",
                        fps=_measured_fps(record) if ours else ""))
    for gid, fs in feeds.items():
        fs.sort(key=lambda f: _FEED_RANK.get(f.time_from, 2))
        # One feed per channel: a guide programme on a channel already listed by
        # name adds no second place to watch (the named listing ranks first).
        seen: set = set()
        feeds[gid] = look_alike_details(
            [f for f in fs if not f.channel_id or not (f.channel_id in seen or seen.add(f.channel_id))])
    ends = {(e.league_key, e.team_a, e.team_b, e.start_utc): e.ended_at
            for e in session.execute(select(GameEndDB)).scalars()}
    league_logos = _league_logos(rows, feed_rows, logos)
    out = []
    for g in rows:
        dto = GameDTO(g.id, g.sport, g.league, g.team_a, g.team_b, g.start_utc, g.level,
                      g.replay, g.collections, tuple(feeds.get(g.id, ())),
                      ended_at=ends.get((f"{g.sport}/{g.league}", g.team_a, g.team_b, g.start_utc)),
                      home=g.home_team or "", league_logo=league_logos.get(g.league, ""))
        if dto.playable:
            out.append(dto)
    return out
