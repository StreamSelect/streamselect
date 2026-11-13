"""The Watch Alerts Sports group and the header's per-kind badges (design: Watch
Alerts Row Grammar, NK-1..NK-4, 2026-11-13).

A real ``WatchAlertsSection`` on a real file database with stored games; the
clock is pinned through the module's ``now_utc``. Assertions are on what is
drawn: which rows exist, bar vs time, where the group sits, what a badge says.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from PyQt6.QtWidgets import QPushButton

from streamselect.core.games.alerts import (
    EITHER_SIDE, THIS_EVENT, EventAlert, add_alert, expired_event_rules, load_alerts, rule_for,
    waiting_events, watched_game_ids,
)
from streamselect.core.games.read import GameDTO, GameFeedDTO, load_games
from streamselect.core.games.store import refresh_games, sport_settings
from streamselect.core.watchlist_matching import ANY_WORD
from tests.conftest import destroy_widget
from tests.test_game_finder import NOW, START, _seed_db

SETTINGS = sport_settings()
LIVE_AT = START + timedelta(minutes=70)


@pytest.fixture
def games_db(db):
    _seed_db(db)
    refresh_games(db, NOW)
    return db


def _game(gid: int, start, a="Minnesota Wild", b="Winnipeg Jets") -> GameDTO:
    feed = GameFeedDTO(f"c{gid}", "x", "US| ESPN+", False, "zone", "p1", "US| ESPN+")
    return GameDTO(gid, "hockey", "NHL", a, b, start, 1, False, 2, (feed,))


# ── core rules ────────────────────────────────────────────────────────────
def test_back_to_back_games_are_two_items_and_each_leaves_on_its_own():
    today, tomorrow = _game(1, START), _game(2, START + timedelta(days=1))
    rule = EventAlert("r", ("Minnesota Wild",), ANY_WORD, "")
    before = START - timedelta(hours=1)
    assert waiting_events([today, tomorrow], [rule], before, SETTINGS, set()) == [today, tomorrow]
    # Today's is watched: it goes, tomorrow's stays, and so does the rule.
    assert waiting_events([today, tomorrow], [rule], before, SETTINGS, {1}) == [tomorrow]
    # Today's is over: it goes by itself.
    after = START + timedelta(hours=5)
    assert waiting_events([today, tomorrow], [rule], after, SETTINGS, set()) == [tomorrow]


def test_a_live_event_is_still_waiting_until_it_is_over():
    g = _game(1, START)
    rule = rule_for(THIS_EVENT, g)
    assert waiting_events([g], [rule], START + timedelta(minutes=70), SETTINGS, set()) == [g]


def test_a_one_event_rule_expires_and_a_standing_rule_never_does():
    g = _game(1, START)
    one = EventAlert("one", (g.team_a, g.team_b), "all", rule_for(THIS_EVENT, g).event)
    standing = EventAlert("standing", (g.team_a,), ANY_WORD, "")
    assert expired_event_rules([one, standing], START + timedelta(hours=11)) == []
    assert expired_event_rules([one, standing], START + timedelta(hours=13)) == ["one"]


def test_a_play_from_just_before_the_start_counts_as_watching(games_db):
    from streamselect.core.playback_models import PlaybackEventDB
    with games_db.session_scope() as s:
        g = next(x for x in load_games(s, "hockey", set(), 1, 2) if x.team_a == "Buffalo Sabres")
        cid = g.playable[0].channel_id
        s.add(PlaybackEventDB(provider_id="p1", channel_id=cid, title="t", outcome="started",
                              started_at=START - timedelta(hours=2)))
    with games_db.session_scope() as s:
        assert watched_game_ids(s, [g]) == set(), "a play hours before is a different programme"
        s.add(PlaybackEventDB(provider_id="p1", channel_id=cid, title="t", outcome="started",
                              started_at=START - timedelta(minutes=10)))
    with games_db.session_scope() as s:
        assert watched_game_ids(s, [g]) == {g.id}


# ── the section ───────────────────────────────────────────────────────────
@pytest.fixture
def section(games_db, qapp, monkeypatch):
    from streamselect.core.config import Config
    from streamselect.gui.sidebar import alerts_sports
    from streamselect.gui.sidebar.alerts import WatchAlertsSection

    clock = {"now": START - timedelta(minutes=30)}
    monkeypatch.setattr(alerts_sports, "now_utc", lambda: clock["now"])
    cfg, _ = Config.load()
    sec = WatchAlertsSection(cfg, games_db)
    sec.resize(300, 600)
    sec.show()
    sec.clock = clock

    def load():
        sec.refresh_sports()
        sec._executor.submit(lambda: None).result()     # one worker: drains the read
        for _ in range(3):
            qapp.processEvents()
    sec.load = load
    yield sec
    sec.shutdown()
    destroy_widget(sec)


def _alert_sabres(db, kind=THIS_EVENT):
    with db.session_scope() as s:
        g = next(x for x in load_games(s, "hockey", set(), 1, 2) if x.team_a == "Buffalo Sabres")
        add_alert(s, rule_for(kind, g, g.team_a))
    return g


def test_sports_sits_directly_under_epg_as_its_own_group(section, games_db):
    _alert_sabres(games_db)
    section.load()
    lay = section.content_layout
    order = [lay.indexOf(w) for w in (section.alerts_tree, section._sports_hdr_container,
                                      section._sports_list, section._vod_list)]
    assert order == sorted(order) and order[1] == order[0] + 1, order
    assert section._sports_hdr_container.isVisible() and section._sports_list.count() == 1


def test_an_upcoming_event_shows_its_time_and_a_live_one_its_bar_never_a_plus_pill(section, games_db):
    _alert_sabres(games_db)
    section.load()
    row = section._sports_list.itemWidget(section._sports_list.item(0))
    assert row.progress is None and row.time_lbl is not None and row.time_lbl.isVisible()
    assert not any(b.text().startswith("+") for b in row.findChildren(QPushButton))

    section.clock["now"] = LIVE_AT
    section.load()
    row = section._sports_list.itemWidget(section._sports_list.item(0))
    assert row.progress is not None and row.progress.isVisible(), "live: the EPG row's bar"
    assert row.progress.width() > 0 and row.time_lbl is None


def test_an_event_leaves_once_it_is_over_and_the_group_hides(section, games_db):
    _alert_sabres(games_db)
    section.clock["now"] = START + timedelta(hours=6)
    section.load()
    assert section._sports_list.count() == 0 and not section._sports_hdr_container.isVisible()


def test_header_badges_are_one_per_kind_with_an_icon_and_no_plus(section, games_db):
    _alert_sabres(games_db)
    section.load()
    sports = section._news_badges["sports"]
    assert sports.isVisible() and sports.text() == "1", "no + in the header (NK-4)"
    assert not sports.icon().isNull(), "the kind's icon leads the number (NK-1)"
    assert not section._news_badges["movies"].isVisible(), "a kind with nothing waiting shows none"
    assert section.header_status() == "", "the shared slot stays empty: the badges say it"
    assert section.news(), "the section still has news, for its height boost"


def test_clicking_the_sports_badge_opens_its_collapsed_group(section, games_db, qapp):
    _alert_sabres(games_db)
    section.load()
    section._toggle_sports_group()
    assert not section._sports_list.isVisible()
    section._news_badges["sports"].click()
    qapp.processEvents()
    assert section._sports_list.isVisible() and section._sports_list.count() == 1


def test_a_bell_rule_for_either_side_lists_every_game_of_that_team(section, games_db):
    g = _alert_sabres(games_db, EITHER_SIDE)
    section.load()
    with games_db.session_scope() as s:
        assert [a.sides for a in load_alerts(s)] == [(g.team_a,)]
    assert section._sports_list.count() >= 1
