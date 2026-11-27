"""Three finder misreadings found by counting the team-less on-now listings (2026-11-27).

* an en dash is a matchup's hyphen ("Hokej na ledu – NHL: Carolina – Seattle",
  one guide's form for every game);
* a stated zone is read with a stated date ("… | Fri 27 Nov 17:55 CET (DE) | …"
  was never placed: zones were read only on dateless listings);
* an all-capitals league word ("AHL") names its league only in capitals where the
  list says ``capitals: true`` — "So'al Ahl Al Thekr" is an Arabic title.
"""

from __future__ import annotations

from datetime import datetime

from streamselect.core import sports_catalog as sc
from streamselect.core.games import finder as F
from streamselect.core.games.finder import GUIDE, ListingIn, SportSettings
from streamselect.core.games.listing_text import acronyms_of, league_matcher, matchups, norm
from streamselect.core.games.teams import TeamBook

NOW = datetime(2026, 11, 27, 19, 20)
NHL = SportSettings("hockey", "NHL", ("NHL",))


def test_an_en_dash_joins_two_sides():
    nhl = league_matcher(["NHL"])
    assert matchups(norm("Hokej na ledu – NHL: Carolina – Seattle"), nhl) == [(("CAROLINA",), ("SEATTLE",))]
    # "Košarka – ABA liga" (sport – league) reads as a pair too; its sides are no known
    # teams, so it makes no game and the book never learns them (measured on the real book).
    assert (("CLUJ",), ("ZADAR",)) in matchups(norm("Košarka — ABA liga: Cluj — Zadar"), league_matcher(["ABA"]))


def test_a_stated_zone_is_read_with_a_stated_date():
    league = league_matcher(NHL.words)
    li = ListingIn("p1", "DE PPV", "LIVE | NHL-MATCHDAY 27.11.2026 - MIT SKY SPORT | Fri 27 Nov 17:55 CET (DE) | PPV 3",
                   "m1", seeded=True)
    work = F._read([li], TeamBook([], [], league), league, NOW)
    F._place_times(work, {}, {}, NOW)
    assert (work[0].utc, work[0].time_from) == (datetime(2026, 11, 27, 16, 55), "zone")


def _seeded(names, settings):
    league = league_matcher(settings.words)
    caps = acronyms_of(settings.words) if settings.capitals else frozenset()
    seeded, _ = F._split([ListingIn(GUIDE, "Guide", n, None, NOW) for n in names], league, caps)
    return [li.name for li in seeded]


def test_an_all_capitals_league_word_counts_only_in_capitals_where_the_list_says_so():
    ahl = next(lg for s in sc.sports() for lg in s.leagues if lg.name == "AHL")
    assert ahl.capitals
    settings = SportSettings("hockey", "AHL", ahl.words, capitals=True)
    assert _seeded(["So'al Ahl Al Thekr", "Live: AHL Hockey"], settings) == ["Live: AHL Hockey"]
    nba = SportSettings("basketball", "NBA", ("NBA",))
    assert _seeded(["Basket Nba Action 2026/2027 Ep.6"], nba) == ["Basket Nba Action 2026/2027 Ep.6"], \
        "a league without capitals: true still reads its word in any case"
