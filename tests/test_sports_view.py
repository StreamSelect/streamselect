"""The Sports view: games on now as cards, every channel of a game listed, later and finished games below.

Built on stored games (the finder runs on a real file database first), with
the clock injected so "on now" is fixed.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLabel

from streamselect.core.games.read import ENDING, ON_NOW, OVER, UPCOMING, best_feed, game_state, load_games
from streamselect.core.games.store import enabled_leagues, refresh_games
from streamselect.core.repositories import RepositoryFactory
from tests.test_game_finder import NOW, START, _seed_db

HOCKEY = next(s for s in enabled_leagues() if s.sport == "hockey")


@pytest.fixture
def games_db(db):
    _seed_db(db)
    refresh_games(db, NOW)
    return db


def _load(db, hidden=frozenset()):
    with db.session_scope(commit=False) as s:
        return load_games(s, "hockey", set(hidden), 1, 1)


def test_a_game_is_on_then_likely_ending_then_over():
    from streamselect.core.games.read import GameDTO
    game = GameDTO(1, "hockey", "NHL", "A", "B", START, 1, False, 2, ())
    assert game_state(game, START - timedelta(minutes=1), HOCKEY) == UPCOMING
    assert game_state(game, START + timedelta(hours=2), HOCKEY) == ON_NOW
    assert game_state(game, START + timedelta(hours=3), HOCKEY) == ENDING
    assert game_state(game, START + timedelta(hours=4), HOCKEY) == OVER


def test_the_best_feed_is_a_named_channel_and_a_switched_off_source_drops_out(games_db):
    games = _load(games_db)
    sabres = next(g for g in games if g.team_a == "Buffalo Sabres")
    assert not best_feed(sabres).from_guide
    assert {f.channel_id for f in sabres.playable} == {"a1", "b1", "c1", "s1"}
    # Turning a source off hides its feeds now, not at the next refresh.
    hidden = _load(games_db, {"p2"})
    sabres = next(g for g in hidden if g.team_a == "Buffalo Sabres")
    assert {f.channel_id for f in sabres.playable} == {"a1", "b1"}


def _view(db, qapp, owned_widgets, now):
    from streamselect.core.config import Config
    from streamselect.gui.sports_view import SportsView

    def run_query(fn, on_result, *, token_ref=None, on_error=None):
        with db.session_scope(commit=False) as s:
            on_result(fn(RepositoryFactory(s)))

    view = owned_widgets.own(SportsView(db, Config(), run_query, clock=lambda: now))
    view.resize(1000, 800)
    view.show()
    view.on_activate()
    qapp.processEvents()
    return view


def _ink(label: QLabel) -> QColor:
    image = label.grab().toImage()
    bg = QColor(image.pixel(0, 0))
    ink = [QColor(image.pixel(x, y)) for x in range(image.width()) for y in range(image.height())
           if QColor(image.pixel(x, y)) != bg]
    assert ink, "the tag draws nothing"
    return max(ink, key=lambda c: c.saturation())


def test_games_on_now_are_live_cards_side_by_side(games_db, qapp, owned_widgets):
    from streamselect.gui import theme
    view = _view(games_db, qapp, owned_widgets, START + timedelta(minutes=70))
    assert [c.game.title for c in view.cards] == ["Buffalo Sabres vs Chicago Blackhawks",
                                                    "Dallas Stars vs Winnipeg Jets"]
    a, b = (c.mapTo(view, QPoint(0, 0)) for c in view.cards)
    assert a.y() == b.y() and b.x() >= a.x() + view.cards[0].width(), "cards share a row"
    tag = view.cards[0].tag
    assert tag.text() == "● LIVE · 1h 10m in"
    ink, accent = _ink(tag), QColor(theme.COLOR_ACCENT)
    assert max(abs(ink.red() - accent.red()), abs(ink.green() - accent.green()),
               abs(ink.blue() - accent.blue())) <= 40, "LIVE is drawn in the accent"
    assert "4 channels" in view.cards[0].meta.text()


def test_selecting_a_game_lists_its_channels_below_and_plays_the_one_clicked(games_db, qapp, owned_widgets):
    view = _view(games_db, qapp, owned_widgets, START + timedelta(minutes=70))
    selected, played = [], []
    view.channelSelected.connect(selected.append)
    view.playRequested.connect(played.append)
    view.cards[0].selected.emit(view.cards[0].game)
    qapp.processEvents()
    qapp.processEvents()
    assert selected == ["a1"]
    assert len(view.feed_buttons) == 4
    card_bottom = view.cards[0].mapTo(view, QPoint(0, view.cards[0].height())).y()
    assert all(b.mapTo(view, QPoint(0, 0)).y() > card_bottom for b in view.feed_buttons)
    assert view.cards[0].property("selected") == "true"
    view.feed_buttons[2].click()
    assert played == [view.feed_buttons[2].property("channel_id")]
    assert played[0] in {"a1", "b1", "c1", "s1"}
    view.cards[1].play.emit(view.cards[1].game)
    assert played[-1] == "a2"


def test_past_its_usual_length_a_game_stays_on_now_marked_likely_ending(games_db, qapp, owned_widgets):
    """Overtime and delays run past the usual length; the game is not dropped, it says so."""
    view = _view(games_db, qapp, owned_widgets, START + timedelta(hours=3))
    assert len(view.cards) == 2
    assert all(c.tag.text().startswith("LIKELY ENDING") for c in view.cards)


def test_after_the_games_end_they_are_dimmed_rows_under_finished(games_db, qapp, owned_widgets):
    from streamselect.gui.sidebar.base import GroupHeading
    view = _view(games_db, qapp, owned_widgets, START + timedelta(hours=5))
    assert view.cards == []
    headings = [h.label.text() for h in view.findChildren(GroupHeading)]
    assert "On now" in headings and "Finished" in headings


def test_sports_takes_recommendeds_place_in_the_top_bar():
    from streamselect.gui.app_header import NAV_CHIP_SPECS
    attrs = [spec[0] for spec in NAV_CHIP_SPECS]
    assert attrs[2] == "sports_chip" and "prefs_chip" not in attrs


def test_recommended_opens_from_a_gear_on_its_sidebar_header(qapp, owned_widgets, tmp_path):
    """Owner, 2026-11-12: Recommended left the top bar for Sports; a gear on the
    sidebar section's header opens it, boxed beside the header's other button."""
    from unittest.mock import MagicMock

    from streamselect.core.config import Config
    from streamselect.gui.sidebar.recommended import RecommendedSection

    sec = owned_widgets.own(RecommendedSection(Config(config_dir=tmp_path), MagicMock()))
    if sec.explore_btn.parent() is None:      # the base keeps it unparented until a host places it
        owned_widgets.own(sec.explore_btn)
    sec.resize(320, 300)
    sec.show()
    qapp.processEvents()
    gear = sec.open_view_button
    assert gear.isVisible() and not gear.icon().isNull()
    assert "Recommended" in gear.toolTip()
    title = sec.findChild(QLabel)
    assert gear.mapTo(sec, QPoint(0, 0)).x() > title.mapTo(sec, QPoint(0, 0)).x() + title.width()
    assert abs(gear.mapTo(sec, QPoint(0, 0)).y() - title.mapTo(sec, QPoint(0, 0)).y()) < 20, "in the header row"
    opened = []
    sec.openViewRequested.connect(lambda: opened.append(True))
    gear.click()
    assert opened == [True]
