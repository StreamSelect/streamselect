"""A channel report is remembered after it stops counting (Sticky Channel Reports).

Owner, 2026-11-19: "we shouldn't forget when channels are reported after 30 days so
the user doesn't have to report them again ... it should be somewhat sticky." A
report counts 30 days x the number of reports; after that the channel went back to
its usual place with no mark. Now a "nothing showing" report is remembered: the
channel ranks below every channel never reported (above one reported now), unless
it is your PREFERRED one, and carries the flag plus "· reported <date>". A real
watch after the latest report, or "Forget reports", forgets it. Design artifact
6DnhwofXupRpjvJzH2C888, Q1-Q9 as recommended.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from streamselect.core.games.read import (
    CHANNEL_REPORTS, DIDNT_PLAY, ON_NOW, WRONG_CONTENT, GameDTO, arrange_feeds, channel_history_key,
    game_key, reported_before,
)
from streamselect.core.games.store import refresh_games
from tests.test_game_finder import NOW, START, _seed_db
from tests.test_sports_view import HOCKEY, LIVE_AT, _card, _feed, _settle

LAPSED = START - timedelta(days=40)          # one report, 30-day window: ran out 10 days ago


@pytest.fixture
def games_db(db):
    """Tonight's seeded games, as the Sports view tests use them."""
    _seed_db(db)
    refresh_games(db, NOW)
    return db


def _dp(at):
    return {"kind": DIDNT_PLAY, "at": at.isoformat(), "collection": "p1|X", "name": "x"}


def _game(*feeds):
    return GameDTO(1, "hockey", "NHL", "A", "B", START, 2, False, 1, feeds)


class TestWhatIsRemembered:

    def test_a_lapsed_nothing_showing_report_is_remembered_with_its_date(self):
        assert reported_before([_dp(LAPSED)], None) == LAPSED

    def test_not_this_game_is_not_remembered(self):
        g = _game(_feed("a", "ONE"))
        wrong = {"kind": WRONG_CONTENT, "at": LAPSED.isoformat(), "game": game_key(g)}
        assert reported_before([wrong], None) is None

    def test_a_real_watch_after_the_latest_report_forgets_it(self):
        assert reported_before([_dp(LAPSED)], LAPSED + timedelta(days=1)) is None
        assert reported_before([_dp(LAPSED)], LAPSED - timedelta(days=1)) == LAPSED

    def test_a_report_that_still_counts_is_not_also_reported_before(self):
        f = arrange_feeds(_game(_feed("a", "ONE")), {CHANNEL_REPORTS: {"a": [_dp(START)]}}, {},
                          START).playable[0]
        assert f.report and f.reported_before is None

    def test_a_watch_recorded_in_the_play_log_forgets_it_through_arrange_feeds(self):
        prefs = {CHANNEL_REPORTS: {"a": [_dp(LAPSED)]}}
        watched = {channel_history_key("a"): (LAPSED + timedelta(days=2), 900, 1)}
        f = arrange_feeds(_game(_feed("a", "ONE")), prefs, watched, START).playable[0]
        assert f.reported_before is None and not f.report


class TestTheThreeTiers:

    def test_never_reported_then_reported_before_then_reported_now(self):
        g = _game(_feed("before", "ONE"), _feed("now", "TWO"), _feed("never", "THREE"))
        prefs = {CHANNEL_REPORTS: {"before": [_dp(LAPSED)], "now": [_dp(START)]}}
        order = [f.channel_id for f in arrange_feeds(g, prefs, {}, START).playable]
        assert order == ["never", "before", "now"]

    def test_your_preferred_channel_beats_its_old_report(self):
        g = _game(_feed("never", "THREE"), _feed("before", "ONE"))
        prefs = {"preferred": "p1|ONE", CHANNEL_REPORTS: {"before": [_dp(LAPSED)]}}
        assert arrange_feeds(g, prefs, {}, START).playable[0].channel_id == "before"

    def test_a_report_that_counts_still_beats_preferred(self):
        g = _game(_feed("now", "ONE"), _feed("never", "THREE"))
        prefs = {"preferred": "p1|ONE", CHANNEL_REPORTS: {"now": [_dp(START)]}}
        assert [f.channel_id for f in arrange_feeds(g, prefs, {}, START).playable] == ["never", "now"]

    def test_reporting_it_again_counts_the_old_reports_too(self):
        """Q5: the third report keeps it down for 90 days, not 30."""
        prefs = {CHANNEL_REPORTS: {"a": [_dp(LAPSED - timedelta(days=40)), _dp(LAPSED), _dp(START)]}}
        f = arrange_feeds(_game(_feed("a", "ONE")), prefs, {}, START + timedelta(days=89)).playable[0]
        assert f.report.startswith("Reported 3 times")


def _row(qapp, owned_widgets, feed):
    from streamselect.gui.game_card import ChannelRow
    host = owned_widgets.own(QWidget())
    lay = QVBoxLayout(host)
    row = ChannelRow(feed, "NHL", preferred=False, playing=False, parent=host)
    lay.addWidget(row)
    host.resize(700, 40)
    host.show()
    qapp.processEvents()
    return host, row


class TestTheRow:

    def test_the_row_shows_the_flag_before_the_name_and_the_date_after_it(self, qapp, owned_widgets):
        feed = replace(_feed("a", "ONE"), reported_before=LAPSED)
        host, row = _row(qapp, owned_widgets, feed)
        flag, name, date = row.report_icon, row.name, row.reported_on
        assert flag is not None and flag.isVisibleTo(host)
        assert date is not None and date.isVisibleTo(host) and date.text().startswith("· reported ")
        x = lambda w: w.mapTo(host, QPoint(0, 0)).x()  # noqa: E731
        assert x(flag) < x(name) < x(date), "flag · name · reported <date>"
        assert flag.geometry().width() > 0 and date.geometry().width() > 0
        assert flag.toolTip().startswith("Reported before (nothing showing)")

    def test_a_channel_reported_now_has_no_date(self, qapp, owned_widgets):
        feed = replace(_feed("a", "ONE"), report="Reported once in NHL games: nothing showing. Listed last.",
                       reported=(DIDNT_PLAY,), reported_before=None)
        _host, row = _row(qapp, owned_widgets, feed)
        assert row.report_icon is not None and row.reported_on is None

    def test_a_plain_row_has_neither(self, qapp, owned_widgets):
        _host, row = _row(qapp, owned_widgets, _feed("a", "ONE"))
        assert row.report_icon is None and row.reported_on is None

    def test_the_menu_says_when_and_forget_reports_is_offered(self, qapp, owned_widgets):
        _host, row = _row(qapp, owned_widgets, replace(_feed("a", "ONE"), reported_before=LAPSED))
        acts = {a.text(): a for a in row.build_context_menu("NHL").actions()}
        info = next(a for t, a in acts.items() if t.startswith("Reported before: nothing showing, last on "))
        assert not info.isEnabled(), "a statement, not an action"
        assert acts["Forget reports"].isEnabled()
        assert not acts["Nothing showing"].isChecked(), "it no longer counts, so it is not ticked"

    def test_the_card_flags_a_channel_reported_before(self, qapp, owned_widgets):
        from streamselect.gui.game_card import GameCard
        host = owned_widgets.own(QWidget())
        lay = QVBoxLayout(host)
        feed = replace(_feed("a", "ONE"), reported_before=LAPSED)
        card = GameCard(GameDTO(1, "hockey", "NHL", "Colorado Avalanche", "Nashville Predators", START,
                                2, False, 1, (feed,)), ON_NOW, START + timedelta(minutes=30),
                        HOCKEY.usual_length, parent=host)
        lay.addWidget(card)
        host.show()
        qapp.processEvents()
        assert card.report_icon is not None and card.report_icon.isVisibleTo(host)
        assert card.report_icon.toolTip().startswith("Reported before")
        assert card.graphicsEffect() is None, "only a channel that shows nothing NOW dims the card"


def test_in_the_view_a_remembered_channel_sits_below_and_forget_reports_clears_it(
        games_db, qapp, owned_widgets):
    from streamselect.core.config import Config
    from streamselect.core.repositories import RepositoryFactory
    from streamselect.gui.game_card import ChannelRow
    from streamselect.gui.sports_view import SportsView

    def run_query(fn, on_result, *, token_ref=None, on_error=None, commit=False):
        with games_db.session_scope(commit=commit) as s:
            result = fn(RepositoryFactory(s))
        on_result(result)

    cfg = Config()
    first = SportsView(games_db, cfg, run_query, clock=lambda: LIVE_AT)
    owned_widgets.own(first)
    first.on_activate()
    top = _card(first, "Sabres").game.playable[0]
    cfg.game_channel_prefs = {"hockey/NHL": {CHANNEL_REPORTS: {top.channel_id: [_dp(LIVE_AT - timedelta(days=40))]}}}

    view = owned_widgets.own(SportsView(games_db, cfg, run_query, clock=lambda: LIVE_AT))
    view.resize(1000, 900)
    view.show()
    view.on_activate()
    _card(view, "Sabres").more_chip.click()
    _settle(qapp)
    rows = sorted(_card(view, "Sabres").findChildren(ChannelRow), key=lambda r: r.mapTo(view, QPoint(0, 0)).y())
    assert rows[-1].feed.channel_id == top.channel_id, "below every channel never reported"
    assert rows[-1].reported_on is not None and rows[-1].reported_on.isVisibleTo(view)
    next(a for a in rows[-1].build_context_menu("NHL").actions() if a.text() == "Forget reports").trigger()
    _settle(qapp)
    rows = _card(view, "Sabres").findChildren(ChannelRow)
    assert all(r.report_icon is None and r.reported_on is None for r in rows)
    assert rows[0].feed.channel_id == top.channel_id, "back at its usual place"


def _ink_rgb(label):
    """The most saturated pixel the flag painted, as (r, g, b)."""
    img = label.grab().toImage()
    best, sat = (0, 0, 0), -1
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            s = max(c.red(), c.green(), c.blue()) - min(c.red(), c.green(), c.blue())
            if s > sat and c.alpha() > 200:
                best, sat = (c.red(), c.green(), c.blue()), s
    return best


def test_a_flag_that_counts_now_is_muted_amber_and_one_reported_before_is_grey(qapp, owned_widgets):
    """Owner, 2026-11-23: the reported flag in a warning colour, "but muted, not too aggressive"."""
    now = replace(_feed("a", "ONE"), report="Reported once in NHL games: nothing showing. Listed last.",
                  reported=(DIDNT_PLAY,))
    _h1, row_now = _row(qapp, owned_widgets, now)
    _h2, row_before = _row(qapp, owned_widgets, replace(_feed("b", "TWO"), reported_before=LAPSED))
    r, g, b = _ink_rgb(row_now.report_icon)
    assert r > b + 40 and g > b + 20, f"amber, not grey: {(r, g, b)}"
    r2, g2, b2 = _ink_rgb(row_before.report_icon)
    assert max(r2, g2, b2) - min(r2, g2, b2) < 25, f"reported before stays grey: {(r2, g2, b2)}"


def test_the_muted_amber_is_quieter_than_a_warning_and_still_visible_in_every_theme():
    from streamselect.gui.theme_palettes import PALETTES

    def lum(h):
        h = h.lstrip("#")
        f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

    def contrast(a, b):
        x, y = sorted((lum(a), lum(b)), reverse=True)
        return (x + 0.05) / (y + 0.05)

    for name, p in PALETTES.items():
        bg = p["COLOR_BG_SECTION"]
        muted, warn = contrast(p["COLOR_WARN_MUTED"], bg), contrast(p["COLOR_WARN"], bg)
        assert muted >= 2.7, f"{name}: the flag must stay visible ({muted:.2f}:1)"
        assert muted < warn * 0.75, f"{name}: muted means clearly quieter than a warning"


def test_an_upcoming_games_channels_line_up_under_its_title_flag_or_not(games_db, qapp, owned_widgets):
    """Owner, 2026-11-23: a flag shifted one channel's name, and the list sat between
    the time column and the game titles. Every row now holds a flag column, and the
    list starts where its game's title does."""
    from streamselect.core.config import Config
    from streamselect.gui.game_card import ChannelRow
    from streamselect.gui.sports_view import SportsView

    def run_query(fn, on_result, *, token_ref=None, on_error=None, commit=False):
        with games_db.session_scope(commit=commit) as s:
            result = fn(RepositoryFactory(s))
        on_result(result)

    from streamselect.core.repositories import RepositoryFactory
    cfg = Config()
    view = owned_widgets.own(SportsView(games_db, cfg, run_query, clock=lambda: START - timedelta(hours=3)))
    view.resize(1000, 900)
    view.show()
    view.on_activate()
    matchup = view.rows[0].text()
    view.rows[0].click()
    _settle(qapp)
    rows = view.findChildren(ChannelRow)
    assert len(rows) >= 2
    cfg.game_channel_prefs = {"hockey/NHL": {CHANNEL_REPORTS: {rows[0].feed.channel_id: [_dp(START)]}}}
    view._render()
    _settle(qapp)
    rows = view.findChildren(ChannelRow)
    title = next(r for r in view.rows if r.text() == matchup)
    x = lambda w: w.mapTo(view, QPoint(0, 0)).x()  # noqa: E731
    flagged = [r for r in rows if r.report_icon is not None]
    assert flagged and len(flagged) < len(rows), "one flagged row among plain ones"
    assert len({x(r.name) for r in rows}) == 1, "a flag never shifts a channel's name"
    assert all(x(r) >= x(title) for r in rows), "the list starts under the game's title"
    assert x(rows[0].name) > x(title), "and its names sit a little inside it"
