"""The Sports view (design: The Sports Desk rev 3, SV-Q17-Q36).

Built on stored games (the finder runs on a real file database first), with
the clock injected so "on now" is fixed. Assertions are on what is drawn:
geometry, the colour of LIVE / PLAYING, which rows exist.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QLabel, QPushButton

from streamselect.core.games.read import (
    ENDING, ON_NOW, OVER, UPCOMING, GameDTO, GameFeedDTO, arrange_feeds, game_state, load_games,
)
from streamselect.core.games.store import enabled_leagues, refresh_games
from streamselect.core.repositories import RepositoryFactory
from tests.test_game_finder import NOW, START, _seed_db

HOCKEY = next(s for s in enabled_leagues() if s.sport == "hockey")
LIVE_AT = START + timedelta(minutes=70)


@pytest.fixture
def games_db(db):
    _seed_db(db)
    refresh_games(db, NOW)
    return db


def _view(db, qapp, owned_widgets, now):
    from streamselect.core.config import Config
    from streamselect.gui.sports_view import SportsView

    def run_query(fn, on_result, *, token_ref=None, on_error=None, commit=False):
        with db.session_scope(commit=commit) as s:
            result = fn(RepositoryFactory(s))
        on_result(result)

    view = owned_widgets.own(SportsView(db, Config(), run_query, clock=lambda: now))
    view.resize(1000, 900)
    view.show()
    view.on_activate()
    qapp.processEvents()
    return view


def _settle(qapp):
    for _ in range(3):
        qapp.processEvents()


def _ink(widget) -> QColor:
    image = widget.grab().toImage()
    bg = QColor(image.pixel(0, 0))
    ink = [QColor(image.pixel(x, y)) for x in range(image.width()) for y in range(image.height())
           if QColor(image.pixel(x, y)) != bg]
    assert ink, "draws nothing"
    return max(ink, key=lambda c: c.saturation())


def _near(a: QColor, b: QColor, tol: int = 40) -> bool:
    return max(abs(a.red() - b.red()), abs(a.green() - b.green()), abs(a.blue() - b.blue())) <= tol


def _card(view, team):
    return next(c for c in view.cards if team in c.game.title)


# ── state and ordering (pure) ─────────────────────────────────────────────

def test_a_game_is_on_then_likely_ending_then_over_and_a_finished_mark_ends_it():
    game = GameDTO(1, "hockey", "NHL", "A", "B", START, 1, False, 2, ())
    assert game_state(game, START - timedelta(minutes=1), HOCKEY) == UPCOMING
    assert game_state(game, START + timedelta(hours=2), HOCKEY) == ON_NOW
    assert game_state(game, START + timedelta(hours=3), HOCKEY) == ENDING
    assert game_state(game, START + timedelta(hours=4), HOCKEY) == OVER
    marked = GameDTO(1, "hockey", "NHL", "A", "B", START, 1, False, 2, (), ended_at=START + timedelta(hours=1))
    assert game_state(marked, START + timedelta(hours=2), HOCKEY) == OVER


def _feed(cid, coll, time_from="zone"):
    return GameFeedDTO(cid, cid, coll, False, time_from, "p1", coll)


def test_feeds_order_preferred_then_last_watched_then_minutes_and_hidden_are_counted():
    g = GameDTO(1, "hockey", "NHL", "A", "B", START, 1, False, 3,
                (_feed("a", "ONE"), _feed("b", "TWO"), _feed("c", "THREE"), _feed("d", "FOUR")))
    history = {"p1|TWO": (datetime(2026, 11, 1), 9000, 9), "p1|THREE": (datetime(2026, 11, 10), 60, 1)}
    assert [f.channel_id for f in arrange_feeds(g, {}, history).playable] == ["c", "b", "a", "d"]
    pref = {"preferred": "p1|FOUR", "hidden_channels": ["a"]}
    arranged = arrange_feeds(g, pref, history)
    assert [f.channel_id for f in arranged.playable] == ["d", "c", "b"]
    assert [f.channel_id for f in arranged.hidden] == ["a"]
    gone = arrange_feeds(g, {"hidden_collections": ["p1|TWO", "p1|THREE"]}, history)
    assert {f.channel_id for f in gone.hidden} == {"b", "c"}


def test_a_short_bail_is_not_the_channel_you_last_watched(games_db):
    """Owner, 2026-11-12: a 27 s try of one channel took over a card whose channel
    should have been the one then watched for minutes."""
    from streamselect.core.games.read import load_watch_history
    from streamselect.core.playback_models import PlaybackEventDB
    with games_db.session_scope() as s:
        s.add(PlaybackEventDB(provider_id="p1", channel_id="b1", outcome="started",
                              started_at=datetime(2026, 11, 13, 1, 30), seconds_watched=600))
        s.add(PlaybackEventDB(provider_id="p2", channel_id="c1", outcome="started",
                              started_at=datetime(2026, 11, 13, 1, 40), seconds_watched=27))
    with games_db.session_scope(commit=False) as s:
        history = load_watch_history(s)
        sabres = next(g for g in load_games(s, "hockey", set(), 1, 1) if g.team_a == "Buffalo Sabres")
    assert history["p2|COLL CLOCK"][0] is None, "a bail sets no last-watched time"
    assert arrange_feeds(sabres, {}, history).playable[0].channel_id == "b1"


def test_a_station_written_in_superscript_letters_reads_as_normal_letters():
    feed = GameFeedDTO("x", "x", "x", False, "", "p", "NORWAY ᴳᴼᴸᴰ ᴿᴬᵂ")
    assert feed.station == "GOLD RAW"


def test_a_switched_off_source_drops_out_at_read_time(games_db):
    with games_db.session_scope(commit=False) as s:
        sabres = next(g for g in load_games(s, "hockey", {"p2"}, 1, 1) if g.team_a == "Buffalo Sabres")
    assert {f.channel_id for f in sabres.playable} == {"a1", "b1"}


# ── the cards ─────────────────────────────────────────────────────────────

def test_games_on_now_are_cards_side_by_side_with_live_in_the_accent_and_a_bar(games_db, qapp, owned_widgets):
    from streamselect.gui import theme
    view = _view(games_db, qapp, owned_widgets, LIVE_AT)
    assert [c.game.title for c in view.cards] == ["Buffalo Sabres vs Chicago Blackhawks",
                                                    "Dallas Stars vs Winnipeg Jets"]
    a, b = (c.mapTo(view, QPoint(0, 0)) for c in view.cards)
    assert a.y() == b.y() and b.x() >= a.x() + view.cards[0].width(), "cards share a row"
    card = view.cards[0]
    assert card.tag.text().endswith("LIVE") and " in" not in card.tag.text()
    assert _near(_ink(card.tag), QColor(theme.COLOR_ACCENT)), "LIVE is drawn in the accent"
    assert card.bar is not None and card.bar.isVisible()
    assert "Started" in card.bar.toolTip() and "usually ends" in card.bar.toolTip()
    assert card.more_chip is not None and card.more_chip.text().endswith("+3")


def test_the_view_never_scrolls_sideways_even_narrow(games_db, qapp, owned_widgets):
    from PyQt6.QtWidgets import QScrollArea
    view = _view(games_db, qapp, owned_widgets, LIVE_AT)
    view.resize(420, 900)
    _settle(qapp)
    scroll = view.findChild(QScrollArea)
    assert scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    for c in view.cards:
        right = c.mapTo(scroll.viewport(), QPoint(c.width(), 0)).x()
        assert right <= scroll.viewport().width(), f"{c.game.title} runs off the edge"


def test_one_click_on_the_play_line_or_a_double_click_on_the_card_plays_the_top_channel(
        games_db, qapp, owned_widgets):
    view = _view(games_db, qapp, owned_widgets, LIVE_AT)
    played = []
    view.playRequested.connect(played.append)
    card = view.cards[0]
    QTest.mouseClick(card.play_line, Qt.MouseButton.LeftButton)
    assert played == [card.top_feed.channel_id]
    QTest.mouseDClick(card, Qt.MouseButton.LeftButton)
    assert played[-1] == card.top_feed.channel_id and len(played) == 2


def test_the_chip_opens_the_game_full_width_first_with_every_channel_and_a_row_click_plays(
        games_db, qapp, owned_widgets):
    from streamselect.gui.game_card import ChannelRow
    view = _view(games_db, qapp, owned_widgets, LIVE_AT)
    _card(view, "Dallas").more_chip.click()
    _settle(qapp)
    opened = view.cards[0]
    assert "Dallas" in opened.game.title, "the open game comes first"
    assert opened.width() > view.cards[1].width() * 2, "and spans the width"
    rows = opened.findChildren(ChannelRow)
    assert len(rows) == len(opened.game.playable)
    played = []
    view.playRequested.connect(played.append)
    QTest.mouseClick(rows[1], Qt.MouseButton.LeftButton)
    assert played == [rows[1].feed.channel_id]
    assert rows[1].pref_chip.isHidden() and rows[1].eye.isHidden(), "controls only on hover"


def test_preferred_is_a_chip_and_becomes_what_the_card_plays(games_db, qapp, owned_widgets):
    from streamselect.gui.game_card import ChannelRow
    view = _view(games_db, qapp, owned_widgets, LIVE_AT)
    _card(view, "Sabres").more_chip.click()
    _settle(qapp)
    row = view.cards[0].findChildren(ChannelRow)[-1]
    target = row.feed
    row.pref_chip.click()
    _settle(qapp)
    assert view.config.game_channel_prefs["hockey/NHL"]["preferred"] == target.collection_key
    card = view.cards[0]
    assert card.top_feed.collection_key == target.collection_key
    shown = [r for r in card.findChildren(ChannelRow) if r.pref_chip and not r.pref_chip.isHidden()]
    assert len(shown) == 1 and shown[0].feed.collection_key == target.collection_key
    assert shown[0].pref_chip.text() == "PREFERRED"


def test_a_hidden_channel_leaves_the_list_but_is_counted_and_comes_back(games_db, qapp, owned_widgets):
    from streamselect.gui.game_card import HIDE_CHANNEL, ChannelRow
    view = _view(games_db, qapp, owned_widgets, LIVE_AT)
    _card(view, "Sabres").more_chip.click()
    _settle(qapp)
    row = view.cards[0].findChildren(ChannelRow)[0]
    gone = row.feed.channel_id
    row.hideRequested.emit(row.feed, HIDE_CHANNEL)
    _settle(qapp)
    card = view.cards[0]
    assert gone not in {r.feed.channel_id for r in card.findChildren(ChannelRow)}
    hidden_btn = next(b for b in card.findChildren(QPushButton) if b.text().startswith("1 hidden channel"))
    hidden_btn.click()
    _settle(qapp)
    back = [r for r in view.cards[0].findChildren(ChannelRow) if r.feed.channel_id == gone]
    assert len(back) == 1
    back[0].unhideRequested.emit(back[0].feed)
    _settle(qapp)
    assert not view.config.game_channel_prefs["hockey/NHL"].get("hidden_channels")


def test_while_a_channel_plays_the_top_line_says_playing_in_green_and_rows_do_not_move(
        games_db, qapp, owned_widgets):
    from streamselect.gui import theme
    from streamselect.gui.game_card import ChannelRow
    view = _view(games_db, qapp, owned_widgets, LIVE_AT)
    _card(view, "Sabres").more_chip.click()
    _settle(qapp)
    before = [r.feed.channel_id for r in view.cards[0].findChildren(ChannelRow)]
    view.set_playing(before[-1])
    _settle(qapp)
    card = view.cards[0]
    assert [r.feed.channel_id for r in card.findChildren(ChannelRow)] == before
    assert card.top_feed.channel_id == before[-1]
    word = next(lbl for lbl in card.play_line.findChildren(QLabel) if lbl.text() == "PLAYING")
    assert _near(_ink(word), QColor(theme.COLOR_OK)), "PLAYING in the playing green"


def test_opening_a_later_game_and_redrawing_does_not_crash(games_db, qapp, owned_widgets):
    """Owner, 2026-11-12: clicking one of tomorrow's games aborted the app — the
    channel list's `hide` signal shadowed QWidget.hide(), which the redraw calls."""
    from streamselect.gui.game_card import ChannelList
    view = _view(games_db, qapp, owned_widgets, START - timedelta(hours=3))
    assert view.rows, "the games are still to come"
    view.rows[0].click()
    _settle(qapp)
    assert view.findChildren(ChannelList), "the row opened its channel list"
    view._render()                       # the redraw that crashed
    view.rows[0].click()                 # and closing it again
    _settle(qapp)


def test_past_its_usual_length_a_game_stays_on_now_marked_likely_ending(games_db, qapp, owned_widgets):
    view = _view(games_db, qapp, owned_widgets, START + timedelta(hours=3))
    assert len(view.cards) == 2
    assert all(c.tag.text() == "LIKELY ENDING" for c in view.cards)


def test_finished_starts_folded_and_the_fold_is_remembered(games_db, qapp, owned_widgets):
    view = _view(games_db, qapp, owned_widgets, START + timedelta(hours=5))
    assert view.cards == [] and "finished" in view.headers and view.rows == []
    view._toggle_fold("finished")
    _settle(qapp)
    assert len(view.rows) == 2
    assert "finished" not in view.config.sports_view_state["folded"]


def test_mark_as_finished_moves_the_game_to_finished(games_db, qapp, owned_widgets):
    view = _view(games_db, qapp, owned_widgets, LIVE_AT)
    dallas = _card(view, "Dallas")
    dallas.finished.emit(dallas.game)
    _settle(qapp)
    assert [c.game.title for c in view.cards] == ["Buffalo Sabres vs Chicago Blackhawks"]


def test_the_sort_order_flips_and_is_remembered(games_db, qapp, owned_widgets):
    view = _view(games_db, qapp, owned_widgets, LIVE_AT)
    assert view.sort_button.text() == "Earliest first"
    first = [c.game.title for c in view.cards]
    view.sort_button.click()
    _settle(qapp)
    assert view.config.sports_view_state["sort"] == "latest"
    assert view.sort_button.text() == "Latest first"
    assert sorted(first) == sorted(c.game.title for c in view.cards)


def test_less_certain_games_appear_dashed_when_the_toggle_is_on(db, qapp, owned_widgets):
    from streamselect.core.database import ChannelDB
    _seed_db(db)
    with db.session_scope() as s:
        s.add(ChannelDB(id="x1", source_id="x1", provider_id="p1", category="COLL ZONE A", media_type="live",
                        name="NHL: Boston Bruins vs Montreal Canadiens | Fri 13 Nov 02:10 CET"))
    refresh_games(db, NOW)
    view = _view(db, qapp, owned_widgets, LIVE_AT)
    assert not any("Bruins" in c.game.title for c in view.cards)
    view.less_certain_chip.click()
    _settle(qapp)
    bruins = _card(view, "Bruins")
    assert bruins.property("certain") == "false"
    assert view.config.sports_view_state["less_certain"] is True


# ── loading, and the Recommended gear ─────────────────────────────────────

def test_before_the_finder_has_looked_it_says_so_instead_of_zero(db, qapp, owned_widgets):
    """Owner, 2026-11-12: on a fresh launch the view said 0 games, then 5 appeared."""
    from streamselect.core.config import Config
    from streamselect.gui.sports_view import SportsView

    pending = []
    view = owned_widgets.own(SportsView(db, Config(), lambda fn, cb, **_: pending.append((fn, cb)),
                                        clock=lambda: NOW))
    view.resize(800, 600)
    view.show()
    view.on_activate()
    qapp.processEvents()

    def texts():
        return [w.text() for w in view.findChildren(QLabel) if w.isVisible()]

    assert "Loading games…" in texts()
    view.set_finding(True)
    fn, cb = pending.pop()
    with db.session_scope(commit=False) as s:
        cb(fn(RepositoryFactory(s)))
    qapp.processEvents()
    assert "Finding games in your channel listings…" in texts()
    assert not view.headers, "no 'On now 0'"
    _seed_db(db)
    refresh_games(db, NOW)
    view.finished_finding()
    assert "Finding games in your channel listings…" in texts(), "no flash of the old list"
    fn, cb = pending.pop()
    with db.session_scope(commit=False) as s:
        cb(fn(RepositoryFactory(s)))
    qapp.processEvents()
    assert len(view.cards) == 2 and "Finding games in your channel listings…" not in texts()


def test_sports_takes_recommendeds_place_in_the_top_bar():
    from streamselect.gui.app_header import NAV_CHIP_SPECS
    attrs = [spec[0] for spec in NAV_CHIP_SPECS]
    assert attrs[2] == "sports_chip" and "prefs_chip" not in attrs


def test_recommended_opens_from_a_gear_on_its_sidebar_header(qapp, owned_widgets, tmp_path):
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
    opened = []
    sec.openViewRequested.connect(lambda: opened.append(True))
    gear.click()
    assert opened == [True]


# ── channel reports (SV-Q37-Q39) ──────────────────────────────────────────

def test_a_report_counts_thirty_days_more_reports_extend_it_and_a_real_watch_cancels_one():
    from streamselect.core.games.read import DIDNT_PLAY, report_text
    g = GameDTO(1, "hockey", "NHL", "A", "B", START, 1, False, 2, ())
    at = datetime(2026, 11, 1)
    one = [{"kind": DIDNT_PLAY, "at": at.isoformat()}]
    assert report_text(one, g, None, at + timedelta(days=29)).startswith("Reported once")
    assert report_text(one, g, None, at + timedelta(days=31)) == ""
    two = one + [{"kind": DIDNT_PLAY, "at": at.isoformat()}]
    assert report_text(two, g, None, at + timedelta(days=59)).startswith("Reported 2 times")
    # watched for real after the report: one report is cancelled
    assert report_text(two, g, at + timedelta(days=1), at + timedelta(days=2)).startswith("Reported once")
    assert report_text(one, g, at + timedelta(days=1), at + timedelta(days=2)) == ""


def test_wrong_content_counts_only_for_the_game_it_was_reported_on():
    from streamselect.core.games.read import WRONG_CONTENT, game_key, report_text
    g = GameDTO(1, "hockey", "NHL", "A", "B", START, 1, False, 2, ())
    other = GameDTO(2, "hockey", "NHL", "C", "D", START, 1, False, 2, ())
    rep = [{"kind": WRONG_CONTENT, "at": START.isoformat(), "game": game_key(g)}]
    assert report_text(rep, g, None, START) and report_text(rep, other, None, START) == ""


def test_reporting_a_channel_puts_it_last_with_its_flag_and_clear_brings_it_back(games_db, qapp, owned_widgets):
    from streamselect.gui.game_card import ChannelRow
    view = _view(games_db, qapp, owned_widgets, LIVE_AT)
    _card(view, "Sabres").more_chip.click()
    _settle(qapp)
    first = view.cards[0].findChildren(ChannelRow)[0]
    menu = first.build_context_menu("NHL")
    texts = [a.text() for a in menu.actions()]
    assert "Report this channel" in texts and "Didn't play" in texts and "Wrong content" in texts
    clear = next(a for a in menu.actions() if a.text() == "Clear bad reports")
    assert not clear.isEnabled(), "nothing to clear yet"
    next(a for a in menu.actions() if a.text() == "Didn't play").trigger()
    _settle(qapp)
    rows = view.cards[0].findChildren(ChannelRow)
    last = max(rows, key=lambda r: r.mapTo(view, QPoint(0, 0)).y())
    assert last.feed.channel_id == first.feed.channel_id, "a reported channel is listed last"
    assert last.report_icon is not None and last.report_icon.isVisibleTo(view)
    assert "didn't play" in last.report_icon.toolTip()
    assert all(r.report_icon is None for r in rows if r is not last), "no clutter on other rows"
    clear = next(a for a in last.build_context_menu("NHL").actions() if a.text() == "Clear bad reports")
    assert clear.isEnabled()
    clear.trigger()
    _settle(qapp)
    assert all(r.report_icon is None for r in view.cards[0].findChildren(ChannelRow))
