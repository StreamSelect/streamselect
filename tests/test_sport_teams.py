"""The team book is stored per league and kept across runs (One Sports List slice 4).

Real file database; the finder runs through ``refresh_games`` as the app runs it.
"""

from __future__ import annotations

from datetime import timedelta

from streamselect.core.database import ChannelDB, EpgProgramDB
from streamselect.core.games.finder import find_games, learn_teams
from streamselect.core.games.models import SportTeamDB
from streamselect.core.games.store import refresh_games
from tests.test_game_finder import NHL, NOW, _seed_db, _two_games


def _teams(db) -> dict[str, SportTeamDB]:
    with db.session_scope(commit=False) as s:
        rows = s.query(SportTeamDB).filter_by(league_key="hockey/NHL").all()
        s.expunge_all()
        return {r.name: r for r in rows}


def test_a_run_stores_the_teams_of_its_games_as_confirmed(db):
    _seed_db(db)
    refresh_games(db, NOW)
    teams = _teams(db)
    for name in ("Buffalo Sabres", "Chicago Blackhawks"):
        assert name in teams
        assert teams[name].last_in_game == NOW, "a side of a stored game is confirmed"
        assert teams[name].first_seen == teams[name].last_seen == NOW
        assert teams[name].runs_seen == 1


def test_a_team_that_leaves_the_listings_is_kept_with_when_it_was_last_seen(db):
    _seed_db(db)
    refresh_games(db, NOW)
    later = NOW + timedelta(hours=1)
    with db.session_scope() as s:       # Buffalo's game is gone from every listing by the next run
        for ch in s.query(ChannelDB).filter(ChannelDB.name.ilike("%sabres%")).all():
            s.delete(ch)
        s.query(EpgProgramDB).filter(EpgProgramDB.title.ilike("%sabres%")).delete()
    refresh_games(db, later)
    teams = _teams(db)
    assert teams["Buffalo Sabres"].last_seen == NOW, "kept, not deleted"
    assert teams["Buffalo Sabres"].runs_seen == 1
    assert teams["Buffalo Sabres"].last_in_game == NOW
    seen_again = [t for t in teams.values() if t.last_seen == later]
    assert seen_again and all(t.runs_seen == 2 and t.first_seen == NOW for t in seen_again)


def test_handing_the_finder_its_book_finds_the_same_games():
    listings = _two_games()
    alone, _, _ = find_games(listings, NHL, NOW)
    given, _, _ = find_games(listings, NHL, NOW, book=learn_teams(listings, NHL))
    assert [(g.title, g.start_utc, g.level) for g in given] == \
        [(g.title, g.start_utc, g.level) for g in alone]


def _unknown(s, cid, name):
    s.add(ChannelDB(id=cid, source_id=cid, provider_id="p1", name=name, media_type="live",
                    special_view="sports", sport_type="unknown"))


def test_a_game_nothing_identified_is_named_by_two_confirmed_teams_of_one_league(db):
    from streamselect.core.games.identify import identify_by_teams

    with db.session_scope() as s:
        for league, name, confirmed in (
                ("hockey/NHL", "Toronto Maple Leafs", True), ("hockey/NHL", "Boston Bruins", True),
                ("basketball/NBA", "Toronto Raptors", True), ("basketball/NBA", "Boston Celtics", True),
                ("basketball/NBA", "Liga", False), ("basketball/NBA", "Miami Heat", True)):
            s.add(SportTeamDB(league_key=league, name=name, first_seen=NOW, last_seen=NOW,
                              last_in_game=NOW if confirmed else None))
        _unknown(s, "u1", "NEXT | TORONTO MAPLE LEAFS VS. BOSTON BRUINS | Fri 27 Nov 12:30 EST (US)")
        _unknown(s, "u2", "CA (SN+ 006) | Toronto @ Boston (2026-11-27 13:00:05)")    # NHL or NBA
        _unknown(s, "u3", "NEXT | LIGA VS. MIAMI HEAT | Fri 27 Nov")                    # Liga unconfirmed
    with db.session_scope() as s:
        assert identify_by_teams(s) == 1
    with db.session_scope(commit=False) as s:
        got = {c.id: (c.sport_type, c.league_name, c.sport_from) for c in s.query(ChannelDB).all()}
    assert got["u1"] == ("hockey", "NHL", "teams")
    assert got["u2"][0] == "unknown", "two leagues fit: left for the catch-all"
    assert got["u3"][0] == "unknown", "a name only the listings gave never identifies"


def test_each_finder_run_names_the_games_its_teams_now_explain(db):
    _seed_db(db)
    with db.session_scope() as s:
        _unknown(s, "u9", "NEXT | WINNIPEG JETS - DALLAS STARS | Thu 12 Nov | 8K EXCLUSIVE")
    refresh_games(db, NOW)
    with db.session_scope(commit=False) as s:
        row = s.get(ChannelDB, "u9")
        assert (row.sport_type, row.league_name, row.sport_from) == ("hockey", "NHL", "teams")


def test_a_former_team_name_is_read_as_the_team_now():
    from streamselect.core.games.listing_text import league_matcher, norm
    from streamselect.core.games.teams import TeamBook, team_display

    league = league_matcher(["NHL"])
    seeds = [norm(n) for n in ("NHL: Utah Mammoth vs Nashville Predators | Fri 27 Nov 8:00 PM ET",
                               "NHL: Utah Hockey Club vs Nashville Predators | Fri 27 Nov 8:00 PM ET",
                               "NHL TEAM| UTAH HOCKEY CLUB")]
    book = TeamBook(seeds, [], league, [("Utah Hockey Club", "Utah Mammoth")])
    names = {team_display(t) for t in book.teams}
    assert "Utah Mammoth" in names and "Utah Hockey Club" not in names
    assert book.resolve(("UTAH", "HOCKEY", "CLUB")) == ([("UTAH", "MAMMOTH")], "exact")


def test_the_list_renames_utah_and_a_stored_former_name_goes(db):
    from streamselect.core import sports_catalog as sc

    nhl = next(lg for s in sc.sports() for lg in s.leagues if lg.name == "NHL")
    assert ("Utah Hockey Club", "Utah Mammoth") in nhl.renamed
    _seed_db(db)
    with db.session_scope() as s:
        s.add(SportTeamDB(league_key="hockey/NHL", name="Utah Hockey Club", first_seen=NOW, last_seen=NOW))
    refresh_games(db, NOW)
    assert "Utah Hockey Club" not in _teams(db)


def test_a_game_listed_under_a_former_name_is_named_by_its_teams(db):
    from streamselect.core.games.identify import identify_by_teams

    with db.session_scope() as s:
        for name in ("Utah Mammoth", "Nashville Predators"):
            s.add(SportTeamDB(league_key="hockey/NHL", name=name, first_seen=NOW, last_seen=NOW,
                              last_in_game=NOW))
        _unknown(s, "u5", "NEXT | UTAH HOCKEY CLUB VS. NASHVILLE PREDATORS | Fri 27 Nov")
    with db.session_scope() as s:
        assert identify_by_teams(s) == 1


# ── words that are never a team's (the kept book, measured 2026-11-27) ──


def test_words_that_are_never_a_teams_name_do_not_reach_the_book():
    from streamselect.core.games.listing_text import league_matcher, matchups, norm
    from streamselect.core.games.teams import TeamBook, team_display

    nba = league_matcher(["NBA"])
    assert matchups(norm("NBA: Basket: NBA herrar New York Knicks - Miami Heat"), nba) == [
        (("NEW", "YORK", "KNICKS"), ("MIAMI", "HEAT"))], "Swedish 'herrar' (men's) is not the team"
    nhl = league_matcher(["NHL"])
    assert matchups(norm("LIVE | NHL-MATCHDAY 27.11.2026 - MIT SKY SPORT | Fri 27 Nov 17:55 CET"),
                    nhl) == [], "a show and its broadcaster are not a game"
    ncaa = league_matcher(["NCAA"])
    book = TeamBook([norm("US (ESPN+ 208) | NCAA Men`s Basketball: UK Basketball: Countdown to Tip_Off")],
                    [], ncaa)
    assert "Uk Basketball" not in {team_display(t) for t in book.teams}


def test_a_stored_misreading_goes_and_a_real_team_stays(db):
    _seed_db(db)
    with db.session_scope() as s:
        for name in ("Matchday", "Herrar Buffalo Sabres"):
            s.add(SportTeamDB(league_key="hockey/NHL", name=name, first_seen=NOW, last_seen=NOW,
                              last_in_game=NOW))
    refresh_games(db, NOW)
    teams = _teams(db)
    assert "Matchday" not in teams and "Herrar Buffalo Sabres" not in teams
    assert teams["Buffalo Sabres"].last_in_game == NOW
