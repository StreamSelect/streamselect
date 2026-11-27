"""Reading one listing's text: matchup sides, a date, a time and its zone label.

General formats only — what a date, a clock time or a zone label looks like,
and the words that join two sides (vs, v, @, at, x, " - "). No source, collection
or channel name appears here; team names are learned elsewhere
(:mod:`streamselect.core.games.teams`) from what this module reads.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta
from typing import NamedTuple, Optional

from streamselect.core.event_datetime import ZONE_LABELS

_MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
_MONTHS_FULL = ("JANUARY FEBRUARY MARCH APRIL MAY JUNE JULY AUGUST SEPTEMBER "
                "OCTOBER NOVEMBER DECEMBER").split()
MONTH_WORD: dict[str, int] = {
    **{m: i + 1 for i, m in enumerate(_MONTHS)},
    **{m: i + 1 for i, m in enumerate(_MONTHS_FULL)},
    "SEPT": 9,
}
_WEEKDAYS = "MON TUE WED THU FRI SAT SUN".split()
_WEEKDAYS_FULL = "MONDAY TUESDAY WEDNESDAY THURSDAY FRIDAY SATURDAY SUNDAY".split()
WEEKDAY_WORD: dict[str, int] = {
    **{d: i for i, d in enumerate(_WEEKDAYS)},
    **{d: i for i, d in enumerate(_WEEKDAYS_FULL)},
    "TUES": 1, "THUR": 3, "THURS": 3,
}


def _alternation(words) -> str:
    return "(" + "|".join(sorted(words, key=len, reverse=True)) + ")"


_MW = _alternation(MONTH_WORD)
_WW = _alternation(WEEKDAY_WORD)
_ZONE_RE = _alternation(ZONE_LABELS)
_TIME_RE = re.compile(
    r"(?<![\d:.])(\d{1,2})(?::(\d{2}))?(?::\d{2})?\s*(AM|PM|A\.M\.|P\.M\.)?(?![\d])")
_SEPARATORS = ("VS", "V", "@", "X", "-", "AT")   # tried in this order within a segment
#: "Away @ Home" / "Away at Home": the side after it is the home team.
HOME_SECOND = ("@", "AT")
_SIDE_SPLIT_RE = re.compile(r"\s+(VS\.?|V|@|X|-|AT)\s+")
#: SQL LIKE patterns one of which every plain-ASCII name stating a matchup
#: contains: a separator from :data:`_SEPARATORS` with a space each side
#: (``_SIDE_SPLIT_RE`` needs whitespace there, and a side on each). "VS." is
#: the one spelling the regex adds. LIKE ignores ASCII case, so these match the
#: raw name the same as the upper-cased :func:`norm` text. A name with any other
#: character (a tab, an accent, full-width letters) cannot be judged by LIKE;
#: :data:`NOT_PLAIN_GLOB` keeps it.
MATCHUP_LIKE_PATTERNS = tuple(f"% {sep} %" for sep in _SEPARATORS) + ("% VS. %",)
#: A GLOB that matches any text holding a character outside printable ASCII.
NOT_PLAIN_GLOB = "*[^ -~]*"
_CLOCK_IN_SIDE_RE = re.compile(r"\d{1,2}(:\d{2}){1,2}\s*(AM|PM)?|\d{1,2}\s*(AM|PM)(?![A-Z])")
#: Words that are never part of a team's name, measured in the kept team book
#: (2026-11-27): "NBA herrar New York Knicks" (Swedish "men's") stored "Herrar New
#: York Knicks"; "NHL-MATCHDAY 27.11.2026 - MIT SKY SPORT" stored two teams, a show
#: and its broadcaster; "UK Basketball: Countdown to Tip_Off" stored "Uk Basketball".
#: HOCKEY is not here: it is a word of "Utah Hockey Club".
NOT_TEAM_WORDS = frozenset({"HERRAR", "DAMER", "HERREN", "DAMEN", "MATCHDAY", "PREGAME",
                            "POSTGAME", "COUNTDOWN", "PRESS", "CONFERENCE", "BASKETBALL"})
_STRIP_WORDS = set(MONTH_WORD) | set(WEEKDAY_WORD) | {"AM", "PM"} | set(ZONE_LABELS) | NOT_TEAM_WORDS
#: A side holding one of these runs of words is a broadcaster or a credit, never a
#: team: "… - MIT SKY SPORT" (German "with Sky Sport"), "M1 Group - Sports to the
#: World presents: FIBA 3x3 …" (a guide title). "SPORT" alone is a club's word
#: ("Sport Recife", Benfica's "Sport Lisboa"), so only "SKY SPORT" is listed.
NOT_A_TEAM: tuple[tuple[str, ...], ...] = (("SPORTS",), ("SKY", "SPORT"))
#: A number that is part of a team's name: digits then 3+ letters ("76ERS", "49ERS"),
#: never an ordinal ("18TH"), a quality mark ("4K", "1080P") or a frame rate ("60FPS").
_NAME_NUMBER_RE = re.compile(r"\d+(?!FPS$)[A-Z]{3,}")


class StatedTime(NamedTuple):
    """A clock time read from a name; ``zone`` is its label when one follows it."""

    hour: int
    minute: int
    zone: Optional[str]


Side = tuple[str, ...]


def norm(text: Optional[str]) -> str:
    """Upper case with accents folded, so "Montréal" and "MONTREAL" are one word.

    Plain ASCII has nothing to fold or recompose, so it skips the per-character
    pass: the finder normalises every live channel name, 160,000 calls a run,
    and that pass was half of the run's time (measured 2026-11-17).
    """
    text = text or ""
    if text.isascii():
        return text.upper()
    # An en or em dash joins two sides as a hyphen does: one guide writes every
    # game "Hokej na ledu – NHL: Carolina – Seattle" (measured 2026-11-27).
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    folded = "".join(c for c in unicodedata.normalize("NFKD", text)
                     if not unicodedata.combining(c))
    return unicodedata.normalize("NFKC", folded).upper()


def league_matcher(words) -> re.Pattern[str]:
    """A whole-word matcher for a sport's league words (applied to :func:`norm` text)."""
    alts = "|".join(map(re.escape, (w.upper() for w in words)))
    return re.compile(r"(?<![A-Z0-9])(?:" + alts + r")(?![A-Z0-9])")


def _nearest_year(month: int, day: int, now: datetime,
                  weekday: Optional[int] = None) -> Optional[datetime]:
    best = None
    for year in (now.year - 1, now.year, now.year + 1):
        try:
            d = datetime(year, month, day)
        except ValueError:
            continue
        if weekday is not None and d.weekday() != weekday:
            continue
        if best is None or abs(d - now) < abs(best - now):
            best = d
    return best


def find_date(u: str, now: datetime) -> Optional[datetime]:
    """The first date a normalised name states, at midnight; the year is the nearest one."""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", u)
    if m:
        try:
            return datetime(*map(int, m.groups()))
        except ValueError:
            return None
    m = re.search(r"(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})(?!\d)", u)
    if m:
        a, b, y = map(int, m.groups())
        opts = []
        for mo, dy in ((a, b), (b, a)):
            try:
                opts.append(datetime(y, mo, dy))
            except ValueError:
                pass
        if opts:
            return min(opts, key=lambda d: abs(d - now))
    wd_m = re.search(rf"(?<![A-Z]){_WW}\.?(?![A-Z])", u)
    wd = WEEKDAY_WORD[wd_m.group(1)] if wd_m else None
    m = re.search(rf"(?<![A-Z0-9])(\d{{1,2}})(?:ST|ND|RD|TH)?\s+{_MW}\.?(?![A-Z])", u)
    if m:
        d = _nearest_year(MONTH_WORD[m.group(2)], int(m.group(1)), now, wd)
        if d:
            return d
    m = re.search(rf"(?<![A-Z]){_MW}\.?\s+(\d{{1,2}})(?:ST|ND|RD|TH)?(?!\d)", u)
    if m:
        d = _nearest_year(MONTH_WORD[m.group(1)], int(m.group(2)), now, wd)
        if d:
            return d
    return None


def find_time(u: str) -> Optional[StatedTime]:
    """The clock time a normalised name states, preferring one that carries a zone label.

    A bare number is not a time: it needs minutes or AM/PM ("8PM", "20:00").
    """
    found: list[StatedTime] = []
    for m in _TIME_RE.finditer(u):
        h, mi, ap = m.group(1), m.group(2), m.group(3)
        if mi is None and ap is None:
            continue
        hour, minute = int(h), int(mi or 0)
        if ap:
            ap = ap.replace(".", "")
            if hour == 12:
                hour = 0
            if ap == "PM":
                hour += 12
        if hour > 23 or minute > 59:
            continue
        z = re.match(rf"\s*\(?\s*{_ZONE_RE}(?![A-Z])", u[m.end():])
        found.append(StatedTime(hour, minute, z.group(1) if z else None))
    if not found:
        return None
    zoned = [t for t in found if t.zone]
    return (zoned or found)[0]


def names_league(text: Optional[str], league: re.Pattern[str], acronyms: frozenset[str]) -> bool:
    """Whether *text* names the league. An acronym league word (all capitals in
    the list, "AHL") counts only where the text writes it in capitals: a guide's
    "So'al Ahl Al Thekr" is an Arabic title, not the AHL (measured 2026-11-27)."""
    for m in league.finditer(norm(text)):
        if m.group() not in acronyms or re.search(rf"(?<![A-Za-z0-9]){re.escape(m.group())}(?![A-Za-z0-9])",
                                                    text or ""):
            return True
    return False


#: Where a channel name's schedule tail starts: " @ Nov 27 8:00 PM :Package 19", a
#: dotted, slashed or ISO date, or a clock time.
_TAIL_RE = re.compile(r"\s+@\s|\s\d{1,2}[./]\d{1,2}[./]\d{4}|\s\d{4}-\d{2}-\d{2}|\s\d{1,2}:\d{2}")


def broadcast_title(name: str, league: re.Pattern[str], acronyms: frozenset[str] = frozenset()) -> str:
    """How a team-less channel listing reads on its card: the part of the name that
    names the league, without its schedule tail ("LIVE | NHL-MATCHDAY 27.11.2026 -
    MIT SKY SPORT | Fri 27 Nov 17:55 CET" -> "NHL-MATCHDAY"; "NHL-studion med
    målextra @ Nov 27 8:00 PM :Viaplay SE 19" -> "NHL-studion med målextra")."""
    parts = [p.strip() for p in re.split(r"[|•]", name or "") if p.strip()]
    part = next((p for p in parts if names_league(p, league, acronyms)), parts[0] if parts else "")
    return _TAIL_RE.split(" " + part, maxsplit=1)[0].strip(" -:")


def acronyms_of(words) -> frozenset[str]:
    """The league words written all in capitals, without spaces ("AHL", "NHL")."""
    return frozenset(w for w in words if w.isupper() and " " not in w)


def segments(u: str) -> list[str]:
    """A name's parts: split on | • ( ) , [ ] and on a colon that is not inside a clock."""
    u = re.sub(r"(?<!\d):|:(?!\d)", "|", u)
    return [s for s in re.split(r"[|•(),\[\]]", u) if s.strip()]


def clean_side(part: str, league: re.Pattern[str]) -> Optional[Side]:
    """The words of one side, without clock times, league words, dates and zone labels."""
    p = _CLOCK_IN_SIDE_RE.sub(" ", part)
    p = league.sub(" ", p)
    # "&" joining letters is part of the name ("TEXAS A&M", ESPN's "TA&M"): split
    # there, it read "TA M", and the "AM" of "TEXAS A M" went as a clock word.
    p = re.sub(r"[^A-Z0-9 &]", " ", p.replace(".", ""))
    p = re.sub(r"(?<![A-Z])&|&(?![A-Z])", " ", p)
    # A number is kept only as part of a name ("76ERS", "49ERS"); bare numbers,
    # ordinals ("18TH") and quality marks ("4K", "1080P") go.
    p = " ".join(w if _NAME_NUMBER_RE.fullmatch(w) else re.sub(r"[0-9]", " ", w) for w in p.split())
    words: list[str] = []
    prev_single = False
    for w in p.split():
        if w in _STRIP_WORDS:
            prev_single = False
            continue
        if len(w) == 1 and prev_single:
            words[-1] += w          # "N Y" -> "NY"
        else:
            words.append(w)
        prev_single = len(w) == 1
    side = tuple(dict.fromkeys(words))
    if any(side[i:i + len(run)] == run for run in NOT_A_TEAM for i in range(len(side))):
        return None
    return side if any(len(w) >= 2 for w in side) else None


def matchups(u: str, league: re.Pattern[str]) -> list[tuple[Side, Side]]:
    """Every (side A, side B) a normalised name states, at most one per segment."""
    return [(a, b) for a, b, _sep in matchups_with_separator(u, league)]


def matchups_with_separator(u: str, league: re.Pattern[str]) -> list[tuple[Side, Side, str]]:
    """:func:`matchups`, each with the word that joined it ("VS", "@", "AT"…): an
    "@" or "AT" says the second side is at home (:data:`HOME_SECOND`)."""
    out: list[tuple[Side, Side, str]] = []
    for seg in segments(u):
        parts = _SIDE_SPLIT_RE.split(" " + seg + " ")
        for sep in _SEPARATORS:
            hit = None
            for i in range(1, len(parts), 2):
                if parts[i].rstrip(".") != sep:
                    continue
                a, b = clean_side(parts[i - 1], league), clean_side(parts[i + 1], league)
                if a and b:
                    hit = (a, b, sep)
                    break
            if hit:
                out.append(hit)
                break
    return out


def candidate_days(now: datetime, hour: int, minute: int) -> list[datetime]:
    """Yesterday, today and tomorrow at a dateless clock time (the caller picks the nearest)."""
    base = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return [base + timedelta(days=k) for k in (-1, 0, 1)]
