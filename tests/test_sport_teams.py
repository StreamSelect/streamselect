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
