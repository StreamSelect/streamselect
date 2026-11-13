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
from streamselect.core.epg_utils import to_local
from streamselect.core.games.store import enabled_leagues, refresh_games
from streamselect.core.repositories import RepositoryFactory
from streamselect.gui.sidebar.base import GroupHeading
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
    assert view.cards == [] and "hockey:finished" in view.headers and view.rows == []
    view._toggle_fold("hockey:finished")
    _settle(qapp)
    assert len(view.rows) == 2
    assert "hockey:finished" not in view.config.sports_view_state["folded"]


def test_each_sport_is_its_own_segment_with_a_header_that_folds(games_db, qapp, owned_widgets):
    """Owner, 2026-11-13: hockey is one segment of Sports, not the whole view —
    every sport with a league gets its own header and its own sections."""
    view = _view(games_db, qapp, owned_widgets, LIVE_AT)
    assert "sport:hockey" in view.headers and "hockey:on_now" in view.headers
    sport_hdr, on_now = view.headers["sport:hockey"], view.headers["hockey:on_now"]
    assert sport_hdr.mapTo(view, QPoint(0, 0)).y() < on_now.mapTo(view, QPoint(0, 0)).y()
    view._toggle_fold("sport:hockey")
    _settle(qapp)
    assert view.cards == [] and "hockey:on_now" not in view.headers, "the whole segment folds"


def test_a_click_anywhere_on_the_sport_header_folds_it(games_db, qapp, owned_widgets):
    """Owner report: only the word "Hockey" folded the segment, not the rest of its header."""
    view = _view(games_db, qapp, owned_widgets, LIVE_AT)
    band = view.headers["sport:hockey"]
    spot = QPoint(band.width() - 20, band.height() // 2)        # empty space at the right
    QTest.mouseClick(band, Qt.MouseButton.LeftButton, pos=spot)
    _settle(qapp)
    assert "sport:hockey" in view._folded() and view.cards == []
    band = view.headers["sport:hockey"]
    meta = next(lb for lb in band.findChildren(QLabel) if "NHL" in lb.text())
    QTest.mouseClick(meta, Qt.MouseButton.LeftButton)
    _settle(qapp)
    assert "sport:hockey" not in view._folded() and view.cards, "a click on the league line opens it"


def test_a_section_header_folds_from_its_caret_its_label_or_empty_space_once_per_click(
        games_db, qapp, owned_widgets):
    """Owner report: clicking the caret did nothing; only the label folded the section."""
    view = _view(games_db, qapp, owned_widgets, START + timedelta(hours=5))
    key = "hockey:finished"                       # foldable; starts folded (SV-Q21)
    assert key in view.headers and key in view._folded()
    view._toggle_fold(key)
    _settle(qapp)

    def click(widget, pos=None):
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton, pos=pos or widget.rect().center())
        _settle(qapp)

    band = view.headers[key]
    caret = band.findChildren(QLabel)[0]                         # the first thing on the band
    assert caret.mapTo(band, QPoint(0, 0)).x() < 20, "the caret leads the band"
    click(caret)
    assert key in view._folded(), "the caret folds"
    click(view.headers[key], QPoint(view.headers[key].width() - 10, 8))
    assert key not in view._folded(), "empty space unfolds"
    from streamselect.gui.sidebar.base import GroupHeading
    click(view.headers[key].findChild(GroupHeading))
    assert key in view._folded(), "the label folds, exactly once per click"


def test_on_now_folds_like_the_other_sections(games_db, qapp, owned_widgets):
    """Owner, 2026-11-13: On now folds too."""
    view = _view(games_db, qapp, owned_widgets, LIVE_AT)
    assert view.cards, "games on now show as cards"
    band = view.headers["hockey:on_now"]
    QTest.mouseClick(band, Qt.MouseButton.LeftButton, pos=QPoint(8, band.height() // 2))
    _settle(qapp)
    assert "hockey:on_now" in view._folded() and view.cards == [], "folded: no cards"
    assert "hockey:on_now" in view.headers, "the header stays to unfold it"


def _copy_game_a_day_earlier(db, team_a: str) -> None:
    from sqlalchemy import select

    from streamselect.core.games.models import GameDB, GameFeedDB
    with db.session_scope() as s:
        g = s.execute(select(GameDB).where(GameDB.team_a == team_a, GameDB.level == 1)).scalars().first()
        new = GameDB(sport=g.sport, league=g.league, team_a=g.team_a, team_b="Ottawa Senators",
                     start_utc=g.start_utc - timedelta(days=1), level=1, replay=False, collections=2)
        s.add(new)
        s.flush()
        for f in s.execute(select(GameFeedDB).where(GameFeedDB.game_id == g.id)).scalars():
            s.add(GameFeedDB(game_id=new.id, channel_id=f.channel_id, source=f.source,
                             collection=f.collection, name=f.name, from_guide=f.from_guide,
                             time_from=f.time_from))


def test_finished_games_from_different_days_get_a_sub_section_per_day(games_db, qapp, owned_widgets):
    """Owner, 2026-11-13: Finished showed times with no day, so games from two days read as one."""
    _copy_game_a_day_earlier(games_db, "Buffalo Sabres")
    view = _view(games_db, qapp, owned_widgets, START + timedelta(hours=5))
    view._toggle_fold("hockey:finished")
    _settle(qapp)
    days = [k for k in view.headers if k.startswith("hockey:finished:")]
    assert len(days) == 2, sorted(view.headers)
    tops = [view.headers[k].mapTo(view, QPoint(0, 0)).y() for k in days]
    labels = [view.headers[k].findChild(GroupHeading).label.text() for k in days]
    assert tops == sorted(tops) and days == sorted(days, reverse=True), "most recent day first"
    assert "Tonight" not in " ".join(labels), labels
    finished = view.headers["hockey:finished"]
    assert all(view.headers[k].findChild(GroupHeading).mapTo(view, QPoint(0, 0)).x()
               > finished.findChild(GroupHeading).mapTo(view, QPoint(0, 0)).x() for k in days), (
        "a day sits indented inside Finished")
    view._toggle_fold(days[1])
    _settle(qapp)
    assert days[1] in view._folded() and days[1] in view.headers


def test_only_todays_finished_games_open_a_channel_list(games_db, qapp, owned_widgets):
    """Owner, 2026-11-13: a game that finished on an earlier day has no channels worth
    opening; one that finished today might still be on (it ran late)."""
    _copy_game_a_day_earlier(games_db, "Buffalo Sabres")
    later = START + timedelta(hours=4)          # every game over; still START's local day
    assert to_local(later).date() == to_local(START).date()
    view = _view(games_db, qapp, owned_widgets, later)
    view._toggle_fold("hockey:finished")
    _settle(qapp)
    today = to_local(later).date()
    past = [r for r in view.rows if "Ottawa Senators" in r.text()]
    same_day = [r for r in view.rows if "Ottawa Senators" not in r.text()]
    assert past and same_day
    earlier_day_rows_are_today = to_local(START - timedelta(days=1)).date() == today
    assert not earlier_day_rows_are_today
    assert all(isinstance(r, QLabel) for r in past), "an earlier day's game is plain text"
    assert all(isinstance(r, QPushButton) for r in same_day), "today's still open their channels"
    same_day[0].click()
    _settle(qapp)
    assert view._open is not None, "today's finished game opens its channel list"


def test_a_finished_games_bell_offers_only_team_and_matchup_alerts(games_db, qapp, owned_widgets):
    """Owner, 2026-11-13: an alert for a game that is over has no point, but an alert
    for its teams does."""
    view = _view(games_db, qapp, owned_widgets, START + timedelta(hours=4))
    view._toggle_fold("hockey:finished")
    _settle(qapp)
    row = next(r for r in view.rows if "Sabres" in r.text())
    labels = [a.text() for a in row.bell.build_menu().actions()]
    assert labels and not any("this event" in t for t in labels), labels
    assert any("every Buffalo Sabres event" in t for t in labels)
    assert any("whenever" in t for t in labels)


def test_finished_games_all_from_one_day_have_no_sub_section(games_db, qapp, owned_widgets):
    view = _view(games_db, qapp, owned_widgets, START + timedelta(hours=5))
    view._toggle_fold("hockey:finished")
    _settle(qapp)
    assert not [k for k in view.headers if k.startswith("hockey:finished:")] and view.rows


def test_a_remembered_finished_fold_from_before_sport_segments_carries_over(games_db, qapp, owned_widgets):
    from streamselect.core.config import Config
    from streamselect.gui.sports_view import SportsView
    cfg = Config()
    cfg.sports_view_state = {"folded": ["finished"]}
    view = owned_widgets.own(SportsView(games_db, cfg, lambda fn, cb, **_: None, clock=lambda: LIVE_AT))
    assert view._folded() == {"hockey:finished"}


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


# ── event alerts: the bell (SV-Q24-Q26, Q42) ──────────────────────────────

def test_an_alert_rule_matches_one_event_either_side_or_the_pair():
    from streamselect.core.games.alerts import EITHER_SIDE, THESE_TWO, THIS_EVENT, rule_for
    g = GameDTO(1, "hockey", "NHL", "Buffalo Sabres", "Chicago Blackhawks", START, 1, False, 2, ())
    later = GameDTO(2, "hockey", "NHL", "Buffalo Sabres", "Chicago Blackhawks", START + timedelta(days=9), 1, False, 2, ())
    other = GameDTO(3, "hockey", "NHL", "Buffalo Sabres", "Dallas Stars", START, 1, False, 2, ())
    this = rule_for(THIS_EVENT, g)
    assert this.matches(g) and not this.matches(later)
    pair = rule_for(THESE_TWO, g)
    assert pair.matches(later) and not pair.matches(other)
    team = rule_for(EITHER_SIDE, g, "Buffalo Sabres")
    assert team.matches(other) and team.label == "Buffalo Sabres" and team.detail == "every event"


def test_the_bell_sets_an_alert_for_this_event_and_lights(games_db, qapp, owned_widgets):
    from streamselect.core.games.alerts import load_alerts
    view = _view(games_db, qapp, owned_widgets, LIVE_AT)
    card = _card(view, "Sabres")
    assert not card.bell.covering
    card.bell.click()
    _settle(qapp)
    with games_db.session_scope(commit=False) as s:
        [rule] = load_alerts(s)
    assert rule.event and rule.sides == ("Buffalo Sabres", "Chicago Blackhawks")
    card = _card(view, "Sabres")
    assert card.bell.covering and "Alert set" in card.bell.toolTip()
    assert not _card(view, "Dallas").bell.covering, "only that event"
    card.bell.click()                       # click again: off
    _settle(qapp)
    with games_db.session_scope(commit=False) as s:
        assert load_alerts(s) == []


def test_a_team_alert_lights_every_event_of_that_team_and_says_alert_on_before_it_starts(
        games_db, qapp, owned_widgets):
    view = _view(games_db, qapp, owned_widgets, START - timedelta(hours=3))   # both still to come
    sabres_row = next(r for r in view.rows if "Sabres" in r.text())
    menu = sabres_row.bell.build_menu()
    next(a for a in menu.actions() if a.text() == "Alert me for every Buffalo Sabres event").trigger()
    _settle(qapp)
    sabres_row = next(r for r in view.rows if "Sabres" in r.text())
    dallas_row = next(r for r in view.rows if "Dallas" in r.text())
    assert sabres_row.bell.covering and not dallas_row.bell.covering
    line = sabres_row.parentWidget()
    assert any(lbl.text() == "ALERT ON" for lbl in line.findChildren(QLabel))
    checked = [a.text() for a in sabres_row.bell.build_menu().actions() if a.isChecked()]
    assert checked == ["Alert me for every Buffalo Sabres event"]


# ── event alert notices (SV-Q43) ──────────────────────────────────────────

def test_an_alerted_event_is_announced_once_before_and_once_at_its_start():
    from streamselect.core.games.alerts import THIS_EVENT, due_notices, rule_for
    g = GameDTO(1, "hockey", "NHL", "A", "B", START, 1, False, 2, ())
    other = GameDTO(2, "hockey", "NHL", "C", "D", START, 1, False, 2, ())
    alerts = [rule_for(THIS_EVENT, g)]
    sent: set = set()
    early = due_notices([g, other], alerts, START - timedelta(minutes=20), 15, sent)
    assert early == []
    lead = due_notices([g, other], alerts, START - timedelta(minutes=14), 15, sent)
    assert [(t) for _k, _g, t in lead] == ["Starting in 14 minutes"]
    sent |= {k for k, _g, _t in lead}
    assert due_notices([g], alerts, START - timedelta(minutes=10), 15, sent) == [], "once"
    start = due_notices([g], alerts, START + timedelta(minutes=1), 15, sent)
    assert [t for _k, _g, t in start] == ["Starting now"]
    assert [t for _k, _g, t in due_notices([g], alerts, START - timedelta(minutes=5), 0, set())] == [], \
        "a lead of 0 sends only the start notice"


def test_the_notifier_shows_the_notice_with_play_on_the_cards_channel(games_db, qapp):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from streamselect.core.config import Config
    from streamselect.core.games.alerts import THIS_EVENT, add_alert, rule_for
    from streamselect.core.games.read import load_games
    from streamselect.gui.event_alert_notifier import EventAlertNotifier
    with games_db.session_scope() as s:
        sabres = next(g for g in load_games(s, "hockey", set(), 1, 1) if g.team_a == "Buffalo Sabres")
        add_alert(s, rule_for(THIS_EVENT, sabres))

    def run_query(fn, cb, **_):
        with games_db.session_scope(commit=False) as s:
            res = fn(RepositoryFactory(s))
        cb(res)

    host = SimpleNamespace(_run_query=run_query, config=Config(), notification_manager=MagicMock())
    played = []
    notifier = EventAlertNotifier(host, played.append, clock=lambda: START - timedelta(minutes=10))
    notifier.check()
    notifier.check()
    assert host.notification_manager.show.call_count == 1, "once"
    kw = host.notification_manager.show.call_args.kwargs
    assert kw["title"] == "Starting in 10 minutes" and "Buffalo Sabres vs Chicago Blackhawks" in kw["message"]
    [(label, play)] = kw["actions"]
    play()
    assert label == "Play" and played == ["a1"]
