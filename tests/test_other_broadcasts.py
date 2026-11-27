"""Other broadcasts on now (design "Other Broadcasts On Now", rev 2, owner 2026-11-27).

A timed listing naming the league but no teams, that joined no game, is stored
by the finder run and shown under the league's On now, behind a Games | All
track. Real file database; the view is the real SportsView.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from PyQt6.QtCore import QPoint

from streamselect.core.database import ChannelDB, EpgProgramDB
from streamselect.core.games.broadcasts import load_broadcasts
from streamselect.core.games.models import GameBroadcastDB
from streamselect.core.games.store import refresh_games, sport_settings
from tests.test_game_finder import NOW, START, _seed_db

MATCHDAY_AT = START - timedelta(minutes=35)          # "01:30 CET" on Fri 13 Nov = 00:30 UTC


@pytest.fixture
def bdb(db):
    _seed_db(db)
    with db.session_scope() as s:
        s.add(ChannelDB(id="m1", source_id="m1", provider_id="p1", media_type="live", category="DE: SPORT EUROPE PPV",
                        name="LIVE | NHL-MATCHDAY 13.11.2026 - MIT SKY SPORT | Fri 13 Nov 01:30 CET (DE) | PPV 3"))
        for cid in ("t1", "t2"):
            s.add(ChannelDB(id=cid, source_id=cid, provider_id="p1", media_type="live", category="CA SPORTS",
                            name=f"CA| SPORTSNET {cid.upper()}"))
            # Two games start at 01:05: the programme shows one of them, nobody can say which.
            s.add(EpgProgramDB(provider_id="p1", channel_epg_id=cid, channel_db_id=cid, channel_name=cid,
                               title="Live: NHL Hockey", start_time=START, stop_time=START + timedelta(hours=3)))
        s.add(EpgProgramDB(provider_id="p1", channel_epg_id="t1", channel_db_id="t1", channel_name="t1",
                           title="NHL Tonight", start_time=START, stop_time=START + timedelta(hours=1)))
        s.add(ChannelDB(id="o2", source_id="o2", provider_id="off", media_type="live", category="OFF",
                        name="LIVE | NHL-MATCHDAY 13.11.2026 | Fri 13 Nov 01:30 CET"))
    refresh_games(db, NOW)
    return db


def test_the_finder_run_stores_the_team_less_listings_no_game_took(bdb):
    with bdb.session_scope(commit=False) as s:
        rows = {(r.channel_id, r.title, r.from_guide, r.start_utc) for r in s.query(GameBroadcastDB)}
    assert rows == {("m1", "NHL-MATCHDAY", False, MATCHDAY_AT),
                    ("t1", "Live: NHL Hockey", True, START), ("t2", "Live: NHL Hockey", True, START)}, \
        "a guide title without Live and a disabled source's listing are not stored"


def test_on_air_is_start_to_the_guides_stop_or_the_usual_length(bdb):
    sports = sport_settings()
    with bdb.session_scope(commit=False) as s:
        now = load_broadcasts(s, sports, {"off"}, NOW)
        later = load_broadcasts(s, sports, {"off"}, START + timedelta(hours=3, minutes=1))
    live = next(b for b in now if b.from_guide)
    assert [c.channel_id for c in live.channels] == ["t1", "t2"], "one programme on two channels is one card"
    assert {b.title for b in now} == {"NHL-MATCHDAY", "Live: NHL Hockey"}
    assert all(b.title != "Live: NHL Hockey" for b in later), "past the guide's stop"
    usual = sports["hockey"].usual_length
    with bdb.session_scope(commit=False) as s:
        assert all(b.title != "NHL-MATCHDAY" for b in load_broadcasts(s, sports, set(), MATCHDAY_AT + usual))


def test_the_more_specific_league_claims_a_listing_two_leagues_match(db):
    _seed_db(db)
    with db.session_scope() as s:
        s.add(ChannelDB(id="n1", source_id="n1", provider_id="p1", media_type="live", name="NBA TV"))
        for league, n in (("NBA", 3), ("G League", 12)):
            s.add(GameBroadcastDB(sport="basketball", league=league, channel_id="n1",
                                  title="Live: NBA G League Basketball", start_utc=START, from_guide=True,
                                  stop_utc=START + timedelta(hours=2), word_len=n, found_at=NOW))
        s.add(GameBroadcastDB(sport="hockey", league="NHL", channel_id="o1", title="hidden source",
                              start_utc=START, found_at=NOW))
    with db.session_scope(commit=False) as s:
        got = load_broadcasts(s, sport_settings(), {"off"}, NOW - timedelta(hours=1))
    assert [(b.league, b.title) for b in got] == [("G League", "Live: NBA G League Basketball")]


# ── the view ─────────────────────────────────────────────────────────────


def _view(db, qapp, owned_widgets, now):
    from streamselect.core.config import Config
    from streamselect.core.repositories import RepositoryFactory
    from streamselect.gui.sports_view import SportsView

    def run_query(fn, on_result, *, token_ref=None, on_error=None, commit=False):
        with db.session_scope(commit=commit) as s:
            result = fn(RepositoryFactory(s))
        on_result(result)

    cfg = Config()
    view = owned_widgets.own(SportsView(db, cfg, run_query, clock=lambda: now))
    view.resize(1000, 1400)
    view.show()
    view.on_activate()
    for _ in range(3):
        qapp.processEvents()
    return view, cfg


def _visible_cards(view):
    from streamselect.gui.broadcast_card import BroadcastCard
    return [c for c in view.findChildren(BroadcastCard) if c.isVisible()]


def test_all_lays_the_broadcasts_out_below_the_games_as_half_height_cards(bdb, qapp, owned_widgets):
    view, _cfg = _view(bdb, qapp, owned_widgets, START + timedelta(minutes=70))
    assert view.show_broadcasts and view.all_chip.is_enabled() and not view.games_chip.is_enabled(), "All by default"
    assert "hockey:NHL:other_broadcasts" in view.headers
    cards = _visible_cards(view)
    assert sorted((c.title.toolTip(), c.source.text(), c.tag.text().split()[-1]) for c in cards) == [
        ("Live: NHL Hockey", "GUIDE", "LIVE"), ("NHL-MATCHDAY", "NAME", "LIVE")]
    games = [c for c in view.cards if c.isVisible()]
    y = lambda w: w.mapTo(view, QPoint(0, 0)).y()      # noqa: E731
    assert games and min(y(c) for c in cards) > max(y(g) + g.height() for g in games), "below every game card"
    assert max(c.height() for c in cards) <= 0.65 * min(g.height() for g in games), "half a game card's height"
    assert all(c.width() == games[0].width() for c in cards), "as wide, so the columns line up"


def test_games_hides_them_everywhere_and_is_remembered(bdb, qapp, owned_widgets):
    view, cfg = _view(bdb, qapp, owned_widgets, START + timedelta(minutes=70))
    view.games_chip.click()
    for _ in range(3):
        qapp.processEvents()
    assert _visible_cards(view) == [] and "hockey:NHL:other_broadcasts" not in view.headers
    assert cfg.sports_view_state["other_broadcasts"] is False
    assert view.games_chip.is_enabled() and not view.all_chip.is_enabled(), "the track stays, so All can come back"


def test_a_card_plays_its_first_channel_and_opens_the_others(bdb, qapp, owned_widgets):
    view, _cfg = _view(bdb, qapp, owned_widgets, START + timedelta(minutes=70))
    played = []
    live = next(c for c in _visible_cards(view) if c.item.from_guide)
    live.play.connect(played.append)
    live.play_line.clicked.emit()
    live.more_chip.click()
    qapp.processEvents()
    assert live.others.isVisible()
    from PyQt6.QtWidgets import QPushButton
    live.others.findChildren(QPushButton)[0].click()
    assert played == ["t1", "t2"]
