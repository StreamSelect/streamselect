"""Team names learned from the listings themselves — never a typed list.

Every side of every matchup in the league's seed listings is a candidate; the
longest form of a name wins and shorter forms, initials and prefixes match it
("TBL", "NYI", "CALGARY" -> "CALGARY FLAMES"). A side that names a team this
book has never seen stays unknown, which is what keeps another sport's
"Florida vs Boston" from joining a hockey game on city names alone.
"""

from __future__ import annotations

import collections
import re
from typing import Iterable, Literal, Optional

from streamselect.core.games.listing_text import Side, clean_side, matchups, segments

Match = Literal["exact", "abbrev"]
Resolution = Literal["exact", "abbrev", "ambiguous", "unknown"]


def _initials_runs(team: Side) -> set[str]:
    return {"".join(w[0] for w in team[i:j])
            for i in range(len(team)) for j in range(i + 1, len(team) + 1)}


def _subsequence(abbr: str, word: str) -> bool:
    it = iter(word)
    return word[:1] == abbr[:1] and all(c in it for c in abbr)


def _same(word: str, team_word: str) -> bool:
    """The same word, or a 5+-letter word with its letters swapped ("PHANTERS" for
    "PANTHERS"): one guide's typo is not another team."""
    return word == team_word or (len(word) >= 5 and sorted(word) == sorted(team_word))


def _as_team(side: Side, team: Side) -> Side:
    """*side* with each word that is a typo of a team word spelt as the team spells it."""
    return tuple(next((t for t in team if _same(w, t)), w) for w in side)


def match(side: Side, team: Side, allow_abbrev: bool = True) -> Optional[Match]:
    """'exact' if every side word is a team word; 'abbrev' via initials or a prefix."""
    side = _as_team(side, team)
    if set(side) <= set(team):
        pos = [team.index(w) for w in side]
        if len(pos) >= 2 and pos == sorted(pos) and pos[-1] - pos[0] > len(pos) - 1:
            return None   # a word inserted between: a different team (BUFFALO JR SABRES)
        return "exact"
    if not allow_abbrev:
        return None
    runs = _initials_runs(team)
    if len(side) == 1 and 2 <= len(side[0]) <= 4:
        w = side[0]
        if w in runs or (len(w) >= 3 and (team[0].startswith(w) or _subsequence(w, "".join(team)))):
            return "abbrev"
        return None
    if all(w in team or (len(w) <= 2 and w in runs) for w in side):
        return "abbrev"
    return None


def _gapped(side: Side, team: Side) -> bool:
    """Every side word is a team word, in order, with a team word left out between."""
    side = _as_team(side, team)
    if not set(side) <= set(team):
        return False
    pos = [team.index(w) for w in side]
    return pos == sorted(pos) and pos[-1] - pos[0] > len(pos) - 1


class TeamBook:
    """The teams of one sport, learned from its seed names and guide titles."""

    def __init__(self, seed_names: Iterable[str], guide_titles: Iterable[str],
                 league: re.Pattern[str]):
        """Learn from normalised names (see :func:`listing_text.norm`)."""
        seed_names = list(seed_names)
        side_count: collections.Counter[Side] = collections.Counter()
        seed_sides: set[Side] = set()
        for i, u in enumerate([*seed_names, *guide_titles]):
            for a, b in matchups(u, league):
                side_count[a] += 1
                side_count[b] += 1
                if i < len(seed_names):
                    seed_sides.update((a, b))
        # A 2-4-word name segment that contains a known side is a longer form of
        # that team ("CALGARY" -> "CALGARY FLAMES").
        longer: collections.Counter[Side] = collections.Counter()
        for u in seed_names:
            for seg in segments(u):
                if matchups(seg, league):
                    continue
                w = clean_side(seg, league)
                if w and 2 <= len(w) <= 4 and any(set(sd) < set(w) for sd in side_count):
                    longer[w] += 1
        side_count.update(longer)
        # A two-word prefix in front of 3+ different sides is a label ("NHL TEAM"),
        # not part of a name. One-word prefixes are usually places ("NEW", "SAN").
        rest: dict[Side, set[Side]] = collections.defaultdict(set)
        for sd in side_count:
            if len(sd) > 2:
                rest[sd[:2]].add(sd[2:])
        self._labels = {pre for pre, tails in rest.items() if len(tails) >= 3 and pre not in side_count}
        merged: collections.Counter[Side] = collections.Counter()
        for sd, n in side_count.items():
            merged[self._unlabel(sd)] += n
        ordered = sorted(merged, key=lambda s: (-len(s), -sum(map(len, s)), -merged[s]))
        self.teams: list[Side] = []
        #: A guide's short form with a word dropped from the middle ("VEGAS
        #: KNIGHTS" for "VEGAS GOLDEN KNIGHTS"). Only a side no seed listing uses:
        #: a seed side with an extra word is a different team (BUFFALO JR SABRES).
        self._short: dict[Side, Side] = {}
        for s in ordered:
            if any(match(s, t) for t in self.teams):
                continue
            gapped = [t for t in self.teams if len(s) >= 2 and _gapped(s, t)]
            if s not in seed_sides and len(gapped) == 1:
                self._short[s] = gapped[0]
                continue
            self.teams.append(s)

    def _unlabel(self, side: Side) -> Side:
        return side[2:] if len(side) > 2 and side[:2] in self._labels else side

    def resolve(self, side: Side, allow_abbrev: bool = True) -> tuple[list[Side], Resolution]:
        """The team(s) a side can mean, and how sure that is."""
        side = self._unlabel(side)
        if side in self._short:
            return [self._short[side]], "exact"
        hits = [(t, k) for t in self.teams if (k := match(side, t, allow_abbrev))]
        exact = [t for t, k in hits if k == "exact"]
        if len(exact) == 1:
            return [exact[0]], "exact"
        if exact:
            return exact, "ambiguous"
        if len(hits) == 1:
            return [hits[0][0]], "abbrev"
        return [t for t, _ in hits], ("ambiguous" if hits else "unknown")


def team_display(team: Side) -> str:
    """"BUFFALO SABRES" -> "Buffalo Sabres"."""
    return " ".join(w.capitalize() for w in team)
