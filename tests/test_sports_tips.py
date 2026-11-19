"""The Sports view's first-time help (owner, 2026-11-18, TQ1-TQ4): a short tour the
first time it shows games, then one-off tips at their moments."""
from __future__ import annotations

import time
from datetime import timedelta

import pytest
from PyQt6.QtCore import QRect, QPoint
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from streamselect.core.repositories import RepositoryFactory
from streamselect.core.games.store import refresh_games
from tests.test_game_finder import NOW, _seed_db
from tests.test_sports_view import LIVE_AT, START


@pytest.fixture
def sports_db(db):
    """The Sports view tests' games (tests/test_sports_view.py ``games_db``)."""
    _seed_db(db)
    refresh_games(db, NOW)
    return db


class _Host(QWidget):
    """The main window as the tips see it: a config, and the Sports view inside."""

    def __init__(self, db, config_dir, now):
        from streamselect.core.config import Config
        from streamselect.gui.sports_view import SportsView
        super().__init__()
        self.resize(1100, 900)
        self.config = Config(config_dir=str(config_dir))

        def run_query(fn, on_result, *, token_ref=None, on_error=None, commit=False):
            with db.session_scope(commit=commit) as s:
                result = fn(RepositoryFactory(s))
            on_result(result)
        lay = QVBoxLayout(self)
        self.sports_view = SportsView(db, self.config, run_query, clock=lambda: now)
        lay.addWidget(self.sports_view)


def _host(db, qapp, owned_widgets, tmp_path, now=LIVE_AT):
    from streamselect.gui.sports_tips import on_league_hidden, on_rendered
    host = owned_widgets.own(_Host(db, tmp_path, now))
    view = host.sports_view
    view.rendered.connect(lambda: on_rendered(host, view))
    view.leagueHidden.connect(lambda sp, lg: on_league_hidden(host, view, sp, lg))
    host.show()
    view.on_activate()
    qapp.processEvents()
    return host, view


def _wait(qapp, cond, secs=3.0):
    end = time.time() + secs
    while not cond() and time.time() < end:
        qapp.processEvents()
        time.sleep(0.02)
    return cond()


def _overlay(host):
    return host.__dict__.get("_tour")


def _ringed(host, widget) -> bool:
    tour = _overlay(host)
    hole = tour.hole()
    return hole is not None and hole.intersects(QRect(widget.mapTo(host, QPoint(0, 0)), widget.size()))


def test_the_first_time_sports_shows_games_its_tour_starts_on_its_own(sports_db, qapp, owned_widgets, tmp_path):
    host, view = _host(sports_db, qapp, owned_widgets, tmp_path)
    assert _wait(qapp, lambda: _overlay(host) is not None), "the tour starts by itself (TQ2)"
    tour = _overlay(host)
    titles = [s.title for s in tour._stops]
    assert titles == ["Sports", "Leagues", "A league", "A game on now", "Alerts", "How games are listed"]
    assert not any("Settings" in s.body for s in tour._stops), "Settings is not in the tour (owner)"
    assert "Less certain" in tour._stops[-1].body
    assert _ringed(host, view.headers["sport:hockey"]), "stop 1 rings the sport header"
    for _ in range(3):
        tour.next()
    assert _ringed(host, view.cards[0]), "stop 4 rings a game on now"
    assert "sports_tour" in host.config.tips_seen
    tour.end()
    qapp.processEvents()
    view._render()
    qapp.processEvents()
    time.sleep(0.7)
    qapp.processEvents()
    assert _overlay(host) is None, "once per profile"


def test_with_no_game_on_now_the_tour_leaves_those_stops_out(sports_db, qapp, owned_widgets, tmp_path):
    host, view = _host(sports_db, qapp, owned_widgets, tmp_path, now=START - timedelta(hours=3))
    assert not view.cards and view.rows
    assert _wait(qapp, lambda: _overlay(host) is not None)
    titles = [s.title for s in _overlay(host)._stops]
    assert "A game on now" not in titles and "Alerts" in titles, "the bell of a game to come instead"


def test_one_off_tips_wait_for_the_tour_then_come_at_their_moment(sports_db, qapp, owned_widgets, tmp_path):
    host, view = _host(sports_db, qapp, owned_widgets, tmp_path)
    assert _wait(qapp, lambda: _overlay(host) is not None)
    _overlay(host).end()
    qapp.processEvents()
    view._toggle_open(view.cards[0].game)                    # a game's channel list opens
    assert _wait(qapp, lambda: _overlay(host) is not None and view.open_list is not None)
    tour = _overlay(host)
    assert tour._title.text() == "A game's channels" and _ringed(host, view.open_list)
    assert "sports_channels" in host.config.tips_seen


def test_hiding_a_league_explains_it_once(sports_db, qapp, owned_widgets, tmp_path):
    host, view = _host(sports_db, qapp, owned_widgets, tmp_path)
    host.config.tips_seen = ["sports_tour", "sports_channels", "sports_finished_bell", "sports_still_on"]
    view._toggle_league("hockey", "NHL")
    assert _wait(qapp, lambda: _overlay(host) is not None)
    assert _overlay(host)._title.text() == "League hidden"
    assert _ringed(host, view.league_chips[("hockey", "NHL")].parentWidget())


def test_changing_a_games_length_in_settings_explains_it_is_kept(qapp, owned_widgets, tmp_path):
    from streamselect.core.config import Config
    from streamselect.gui.settings_dialog import SettingsDialog
    dlg = owned_widgets.own(SettingsDialog(Config(config_dir=tmp_path)))
    dlg._nav.select_by_label("Sports")
    dlg.resize(1100, 860)
    dlg.show()
    qapp.processEvents()
    page = dlg._sports_page
    page.select_sport("hockey")
    qapp.processEvents()
    page.rows["report_days"].editor.setValue(14)
    qapp.processEvents()
    time.sleep(0.7)
    qapp.processEvents()
    assert dlg.__dict__.get("_tour") is None, "only a game's length"
    page.rows["usual_length"].editor.setTime(page.rows["usual_length"].editor.time().addSecs(600))
    assert _wait(qapp, lambda: dlg.__dict__.get("_tour") is not None)
    tour = dlg._tour
    assert tour._title.text() == "Game length"
    row = page.rows["usual_length"].box
    assert tour.hole().intersects(QRect(row.mapTo(dlg, QPoint(0, 0)), row.size()))


def test_opening_finished_games_explains_their_bell_then_still_on(sports_db, qapp, owned_widgets, tmp_path):
    host, view = _host(sports_db, qapp, owned_widgets, tmp_path, now=START + timedelta(hours=4))
    host.config.tips_seen = ["sports_tour", "sports_channels"]
    key = next(k for k in view.headers if k.endswith(":finished"))
    view._toggle_fold(key)                                   # Finished starts folded: open it
    assert _wait(qapp, lambda: _overlay(host) is not None)
    finished = next(r for r in view.rows if r.finished)
    assert _overlay(host)._title.text() == "Alerts after a game" and _ringed(host, finished.bell)
    _overlay(host).end()
    qapp.processEvents()
    assert any(r.still_on for r in view.rows), "a finished game that can still be put back"
    view._render()
    assert _wait(qapp, lambda: _overlay(host) is not None)
    assert _overlay(host)._title.text() == "Still playing?"
