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
