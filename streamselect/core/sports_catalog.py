"""The one sports list: sport ▸ league ▸ words, and every rule that reads it.

``streamselect/data/sports_definitions.yaml`` is the only definition of the sports
the app knows (design "One Sports List", 2026-11-27). Everything that asks "what
sport is this?" comes here:

- :func:`is_sports` — whether a live channel belongs in Sports at all;
- :func:`classify` — the sport, league and provenance stored on a channel at
  ingestion (``special_content.update_channel_special_content``);
- :func:`finder_leagues` — the leagues the game finder runs (``games/store.py``);
- :func:`all_words` — the guide's "Sports" content type (``epg_channel_classify``);
- :func:`sport_label` — how a stored ``sport_type`` reads on screen.

Before this module there were five vocabularies (the sports gate, the sport words,
the league words, PPV's own map and the finder's leagues) plus a Python mirror of
two of them, and they disagreed: a league could sit under another sport (UFC
under boxing), and PPV wrote ``'football'`` for American football.

The bundled file is read once per process. There is no user override file: a
user's own leagues will live in the profile database (roadmap, One Sports List
step 6).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

#: The bundled definitions (also the home of ``sport_defaults``, core/games/tuning.py).
BUNDLED_DEFINITIONS = Path(__file__).parent.parent / "data" / "sports_definitions.yaml"

#: Stored ``sport_type`` values that are not a sport.
NETWORK = "network"     # a sports channel that carries many sports
SLOT = "slot"           # a numbered event slot: empty, or with nothing naming its sport
UNKNOWN = "unknown"     # a sports listing nothing identified (the catch-all's rows)

#: Stored ``sport_from`` values: where a row's sport came from.
FROM_WORD = "word"                  # a word that says the sport
FROM_LEAGUE = "league"              # a league's name
FROM_LEAGUE_GUESS = "league_guess"  # a shared league name, nothing else naming the sport
FROM_LABEL = "label"                # only the slot's own name ("SOCCER PPV 80"): a guess
FROM_TEAMS = "teams"                # both sides are confirmed teams of one league (games/identify.py)
#: How each ``sport_from`` reads (Library breakdown, "Decided by").
FROM_WORDS = {FROM_WORD: "its name", FROM_LEAGUE: "a league", FROM_LEAGUE_GUESS: "a shared league (guess)",
              FROM_LABEL: "slot name (guess)", FROM_TEAMS: "its teams"}

FINDER_LISTED, FINDER_TRIAL, FINDER_OFF = "listed", "trial", "off"

_KIND_LABELS = {NETWORK: "Many sports", SLOT: "Event slot", UNKNOWN: "Unknown"}
#: The stored kinds, in the order they are listed.
KINDS = tuple(_KIND_LABELS)


def is_kind(sport_type: Optional[str]) -> bool:
    """Whether a stored ``sport_type`` is a kind (network, slot, unknown), not a sport."""
    return sport_type in _KIND_LABELS


@dataclass(frozen=True)
class League:
    """One league of one sport."""

    sport: str
    name: str
    words: tuple[str, ...]
    gates: bool = False
    shared: bool = False
    finder: str = FINDER_OFF
    #: (a team's former name, its name now), from the list's ``renamed:``.
    renamed: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Sport:
    """One sport: the words that say it, and its leagues."""

    key: str
    name: str
    words: tuple[str, ...]
    leagues: tuple[League, ...]


@dataclass(frozen=True)
class SportTag:
    """What :func:`classify` decided for one listing."""

    sport_type: str
    league_name: Optional[str] = None
    sport_from: Optional[str] = None


@dataclass(frozen=True)
class _Entry:
    order: int              # file order, for ties
    sport: str
    league: Optional[League]


class _Matcher:
    """One regex over many words; each word has its own capture group.

    ``word*`` matches at the start of a word, any other word matches whole. The
    guards are on letters and digits, not ``\\b``: several words end in a digit
    ("f1", "ligue 1") or contain spaces and punctuation ("sm-liiga", "b.league").
    """

    def __init__(self, words: list[str]):
        #: token -> the words as written that spell it ("f1*" and "F1" share "f1").
        self.forms: dict[str, list[str]] = {}
        for w in words:
            token = w.rstrip("*").strip().lower()
            if token and w not in self.forms.setdefault(token, []):
                self.forms[token].append(w)
        # Longest first, so at one position the longer word is the one matched. A
        # token written both ways is matched as a stem; whole-word forms are then
        # credited only where the match ends a word.
        self.words = sorted(self.forms, key=lambda t: (-len(t), t))
        alts = []
        for t in self.words:
            stem = any(w.endswith("*") for w in self.forms[t])
            alts.append(f"(?<![a-z0-9])({re.escape(t)})" + ("" if stem else "(?![a-z0-9])"))
        self._re = re.compile("|".join(alts)) if alts else None

    def find(self, text: str) -> list[tuple[str, int]]:
        """Every (word as written in the file, matched length) in *text* (lower case)."""
        if self._re is None or not text:
            return []
        out = []
        for m in self._re.finditer(text):
            end = m.end()
            whole = end == len(text) or not text[end].isalnum()
            out += [(w, end - m.start()) for w in self.forms[self.words[m.lastindex - 1]]
                    if whole or w.endswith("*")]
        return out

    def search(self, text: str) -> bool:
        return bool(self._re and text and self._re.search(text))


@dataclass(frozen=True)
class Catalog:
    """The parsed file and the matchers built from it."""

    sports: tuple[Sport, ...]
    by_word: dict              # word as written -> tuple[_Entry, ...]
    tag: _Matcher              # sport words + league words
    gate: _Matcher             # sport words + gating league words + network words
    network: _Matcher
    labels: tuple[re.Pattern, ...]
    numbered: tuple[re.Pattern, ...]
    empty: _Matcher


def _strs(items) -> tuple[str, ...]:
    return tuple(str(w) for w in (items or ()) if str(w).strip())


def _parse(data: dict) -> Catalog:
    sports: list[Sport] = []
    by_word: dict[str, list[_Entry]] = {}
    tag_words: list[str] = []
    gate_words: list[str] = []
    order = 0
    for key, body in (data.get("sports") or {}).items():
        body = body or {}
        words = _strs(body.get("words"))
        leagues = []
        for name, lb in (body.get("leagues") or {}).items():
            lb = lb or {}
            finder = str(lb.get("finder") or FINDER_OFF)
            if finder not in (FINDER_LISTED, FINDER_TRIAL, FINDER_OFF):
                raise ValueError(f"sports.{key}.leagues.{name}: finder must be listed, trial or off")
            renamed = tuple((str(old), str(new)) for old, new in (lb.get("renamed") or {}).items())
            if any(not old.strip() or not new.strip() for old, new in renamed):
                raise ValueError(f"sports.{key}.leagues.{name}: renamed needs a former and a current name")
            leagues.append(League(key, str(name), _strs(lb.get("words")), bool(lb.get("gates")),
                                  bool(lb.get("shared")), finder, renamed))
        sports.append(Sport(str(key), str(body.get("name") or key), words, tuple(leagues)))
        for w in words:
            by_word.setdefault(w, []).append(_Entry(order, key, None))
            order += 1
        tag_words += words
        gate_words += words
        for lg in leagues:
            for w in lg.words:
                by_word.setdefault(w, []).append(_Entry(order, key, lg))
                order += 1
            tag_words += lg.words
            if lg.gates:
                gate_words += lg.words
    network_words = list(_strs((data.get("networks") or {}).get("words")))
    slots = data.get("slots") or {}
    return Catalog(
        sports=tuple(sports),
        by_word={w: tuple(e) for w, e in by_word.items()},
        tag=_Matcher(tag_words),
        gate=_Matcher(gate_words + network_words),
        network=_Matcher(network_words),
        labels=tuple(re.compile(p, re.IGNORECASE) for p in _strs(slots.get("labels"))),
        numbered=tuple(re.compile(p, re.IGNORECASE) for p in _strs(slots.get("numbered"))),
        empty=_Matcher(list(_strs(slots.get("empty")))),
    )


@lru_cache(maxsize=1)
def raw() -> dict:
    """The bundled file as read (``sport_defaults`` is read from here too)."""
    with open(BUNDLED_DEFINITIONS) as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def catalog() -> Catalog:
    """The one list. A missing or broken bundled file is a packaging error and raises."""
    return _parse(raw())


def sports() -> tuple[Sport, ...]:
    return catalog().sports


def finder_leagues() -> tuple[League, ...]:
    """The leagues the game finder runs (finder: listed or trial), in file order."""
    return tuple(lg for s in sports() for lg in s.leagues if lg.finder != FINDER_OFF)


def all_words() -> tuple[str, ...]:
    """Every sport and league word, lower case, without the ``*`` marker."""
    return tuple(w.rstrip("*").strip().lower() for w in catalog().tag.words)


def sport_label(sport_type: Optional[str]) -> str:
    """How a stored ``sport_type`` reads: the sport's name, or the kind's."""
    if not sport_type:
        return ""
    if sport_type in _KIND_LABELS:
        return _KIND_LABELS[sport_type]
    for s in sports():
        if s.key == sport_type:
            return s.name
    return str(sport_type).replace("_", " ").strip().title()


def is_sports(name: str, category: str = "") -> bool:
    """Whether a live channel's name or category says Sports: a sport word, a
    gating league word or a network word."""
    gate = catalog().gate
    return gate.search((name or "").lower()) or gate.search(_category(category))


def _category(category: Optional[str]) -> str:
    return (category or "").lstrip("#").strip().lower()


def split_slot_label(name: str) -> tuple[str, str]:
    """(the name without its slot label parts, the label parts) — split on "|"."""
    labels = catalog().labels
    kept, dropped = [], []
    for part in (name or "").split("|"):
        (dropped if part.strip() and any(p.search(part.strip()) for p in labels) else kept).append(part)
    return "|".join(kept), "|".join(dropped)


def _tier(e: _Entry) -> int:
    """A league's name is more specific than a sport word ("Football: NFL
    Gameday" is American football; "Oakland Athletics" on an MLB channel is
    baseball), and a shared league name is the weakest evidence of all."""
    if e.league is None:
        return 1
    return 2 if e.league.shared else 0


def _best(matches: list[tuple[str, int]], by_word: dict) -> list[tuple[int, int, int, _Entry]]:
    """Every entry matched, as (tier, -length, order, entry), best first."""
    out = [(_tier(e), -length, e.order, e) for word, length in matches for e in by_word.get(word, ())]
    return sorted(out, key=lambda t: t[:3])


def _decide(ranked) -> Optional[SportTag]:
    if not ranked:
        return None
    e = ranked[0][3]
    sport = e.sport
    source = FROM_WORD if e.league is None else (FROM_LEAGUE_GUESS if e.league.shared else FROM_LEAGUE)
    league = next((x.league.name for *_k, x in ranked if x.league is not None and x.sport == sport), None)
    return SportTag(sport, league, source)


def classify(name: str, category: str = "", names_a_matchup: bool = False) -> SportTag:
    """The sport, league and provenance of one sports listing.

    The rules, in order (design "One Sports List", OL-Q4–Q10):

    1. A slot's own name ("US: SOCCER PPV 80") is set aside: the rest of the
       name and the category decide.
    2. The name decides; the category only when the name names no sport.
    3. A league's name beats a sport word, a sport word beats a shared league
       name ("Premier League", stored as a guess); within each, the longest
       word wins and ties go to the sport listed first. A league word names
       its own sport.
    4. The league is the best league word OF THAT SPORT; a league of another
       sport is never stored under it.
    5. Nothing named a sport: the slot's own name may, as a guess.
    6. Still nothing: a slot (empty, numbered, or a slot label with no event
       named), a network channel (a network word in the name or category), or
       unknown. A
       listing that names a matchup is unknown, never a network or a slot: it
       is a game nothing identified.
    """
    cat = catalog()
    text, label = split_slot_label(name or "")
    # The listing's own name first; its collection only when the name names no
    # sport ("FOOTBALL PPV" collections carry NFL, handball and F1).
    tag = (_decide(_best(cat.tag.find(text.lower()), cat.by_word))
           or _decide(_best(cat.tag.find(_category(category)), cat.by_word)))
    if tag is not None:
        return tag
    guess = _decide(_best(cat.tag.find(label.lower()), cat.by_word))
    if guess is not None:
        return SportTag(guess.sport_type, guess.league_name, FROM_LABEL)

    if names_a_matchup:
        return SportTag(UNKNOWN)
    lower = (name or "").lower()
    if (label or cat.empty.search(lower)
            or any(p.search((name or "").strip()) for p in cat.numbered)):
        return SportTag(SLOT)
    if cat.network.search(text.lower()) or cat.network.search(_category(category)):
        return SportTag(NETWORK)
    return SportTag(UNKNOWN)
