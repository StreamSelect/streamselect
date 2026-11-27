"""A game nothing identified, named by its two teams: both confirmed teams of one league.

Library Breakdown BV-Q10 (owner, 2026-11-27). A sports listing whose name
states a matchup but no sport word or league ("NEXT | TORONTO MAPLE LEAFS VS.
BOSTON BRUINS | …") is stored ``unknown`` at ingestion, which cannot know the
teams. After every game-finder run the stored team book (``sport_teams``) can:
when both sides are confirmed teams (a side of a stored game) of exactly one
league, the row takes that league's sport and league, with ``sport_from =
"teams"`` — an inference, labelled as one. A matchup two leagues fit
("Toronto @ Boston": NHL or NBA) stays unknown, and an unconfirmed name from
the listings ("Liga") never identifies anything.

Ingestion re-derives a renamed row (rename-clear), so a row's ``teams`` tag
lasts until its name changes and the next run checks it again.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional

from loguru import logger
from sqlalchemy import select

from streamselect.core import sports_catalog
from streamselect.core.database import ChannelDB
from streamselect.core.fixture_titles import parse_fixture_opponents
from streamselect.core.games.listing_text import Side, clean_side, league_matcher, norm
from streamselect.core.games.models import SportTeamDB
from streamselect.core.games.teams import match

#: The special views whose rows carry a sport (special_content).
_VIEWS = ("sports", "ppv", "live_event")


class _League:
    """One league's confirmed teams, indexed by word for a quick candidate list."""

    def __init__(self, key: str, names: list[str], words: tuple[str, ...]):
        self.sport, self.name = key.split("/", 1)
        self.pattern: re.Pattern[str] = league_matcher(words) if words else re.compile(r"(?!x)x")
        self.teams: list[Side] = [tuple(norm(n).split()) for n in names]
        self._by_word: dict[str, list[Side]] = defaultdict(list)
        for t in self.teams:
            for w in set(t):
                self._by_word[w].append(t)

    def team(self, side_text: str) -> Optional[Side]:
        """The one team this side names exactly, or None (unknown, or more than one)."""
        side = clean_side(norm(side_text), self.pattern)
        if not side:
            return None
        candidates = {t for w in side for t in self._by_word.get(w, ())}
        exact = [t for t in candidates if match(side, t, allow_abbrev=False) == "exact"]
        return exact[0] if len(exact) == 1 else None


def _leagues(session) -> list[_League]:
    confirmed: dict[str, list[str]] = defaultdict(list)
    for key, name in session.execute(select(SportTeamDB.league_key, SportTeamDB.name)
                                     .where(SportTeamDB.last_in_game.is_not(None))):
        confirmed[key].append(name)
    words = {f"{lg.sport}/{lg.name}": lg.words for s in sports_catalog.sports() for lg in s.leagues}
    return [_League(key, names, words.get(key, ())) for key, names in confirmed.items()]


def league_of(name: str, leagues: list[_League]) -> Optional[_League]:
    """The one league whose confirmed teams are both sides of *name*'s matchup."""
    a, b = parse_fixture_opponents(name or "")
    if a is None or b is None:
        return None
    fits = [lg for lg in leagues if (ta := lg.team(a)) and (tb := lg.team(b)) and ta != tb]
    return fits[0] if len(fits) == 1 else None


def identify_by_teams(session) -> int:
    """Tag the unknown sports rows two confirmed teams name. Returns how many."""
    leagues = _leagues(session)
    if not leagues:
        return 0
    rows = session.execute(select(ChannelDB).where(
        ChannelDB.sport_type == sports_catalog.UNKNOWN, ChannelDB.special_view.in_(_VIEWS))).scalars()
    found = 0
    for ch in rows:
        lg = league_of(ch.name, leagues)
        if lg is not None:
            ch.sport_type, ch.league_name, ch.sport_from = lg.sport, lg.name, sports_catalog.FROM_TEAMS
            found += 1
    if found:
        logger.info("Sports: {} unidentified games named by two teams of one league", found)
    return found
