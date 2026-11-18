"""System tray ("Tray Mode" design, TQ1-TQ14): what it lists, when it notifies,
what a close does, and the Settings page."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import QApplication, QWidget

from streamselect.core import tray_state
from streamselect.core.notifications import NotificationManager
from streamselect.core.tray_state import TrayItem
from streamselect.gui import main_window_tray, tray as tray_mod
from streamselect.gui.event_alert_notifier import alerted_items
from tests.conftest import destroy_widget, settings_config_double

NOW = datetime(2026, 11, 16, 18, 0)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _item(title, minutes, live=False, target="view:sports"):
    return TrayItem(NOW + timedelta(minutes=minutes), title, "NHL", target, live=live)


# ── pure state ───────────────────────────────────────────────────────────────

def test_menu_lists_live_first_then_by_start_within_12_hours_at_most_five():
    items = [_item("Late", 13 * 60), _item("B", 90), _item("A", 30), _item("Live", -40, live=True),
             _item("C", 120), _item("D", 150), _item("E", 180), _item("Gone", -30)]
    got = [i.title for i in tray_state.menu_items(items, NOW)]
    assert got == ["Live", "A", "B", "C", "D"]


def test_menu_shows_a_repeated_programme_once():
    got = tray_state.menu_items([_item("Same", 30), _item("same", 30, target="view:epg")], NOW)
    assert len(got) == 1


def _show(title, minutes, live=False):
    return TrayItem(NOW + timedelta(minutes=minutes), title, "Comedy Ch", "view:epg", live=live)


def _game(title, minutes, live=False):
    return TrayItem(NOW + timedelta(minutes=minutes), title, "NHL", "view:sports", live=live,
                    kind=tray_state.KIND_GAME)


def test_games_get_their_own_section_first_and_live_shows_cannot_push_them_out():
    shows = [_show(f"Show {n}", -10, live=True) for n in range(6)]
    sections = tray_state.menu_sections(shows + [_game("Kraken vs Jets", 35)], NOW)
    assert [h for h, _ in sections] == ["Sports alerts", "Watch Alerts"]
    assert [i.title for i in sections[0][1]] == ["Kraken vs Jets"]
    assert len(sections[1][1]) == tray_state.MENU_LIMIT


def test_a_show_rerun_all_evening_is_listed_once_at_its_live_airing():
    reruns = [_show("Sitcom", m) for m in (30, 60, 90)] + [_show("Sitcom", -10, live=True)]
    [(_heading, items)] = tray_state.menu_sections(reruns, NOW)
    assert len(items) == 1 and items[0].live


def test_live_items_read_live_and_upcoming_items_read_their_time():
    assert _item("X", -5, live=True).label().startswith("LIVE")
    assert not _item("X", 30).label().startswith("LIVE")


def test_pause_choices_and_their_end():
    hour = tray_state.pause_value(tray_state.PAUSE_HOUR, NOW)
    assert tray_state.paused_until(hour, NOW) == NOW + timedelta(hours=1)
    assert tray_state.paused_until(hour, NOW + timedelta(hours=2)) is None   # it ran out
    tomorrow = datetime.fromisoformat(tray_state.pause_value(tray_state.PAUSE_TOMORROW, NOW))
    assert NOW < tomorrow <= NOW + timedelta(hours=24)
    forever = tray_state.pause_value(tray_state.PAUSE_INDEFINITE, NOW)
    assert tray_state.paused_until(forever, NOW + timedelta(days=30)) == tray_state.PAUSE_INDEFINITE
    assert tray_state.paused_until("not a time", NOW) is None
    assert tray_state.pause_text("", NOW) == ""


def test_tooltip_names_what_plays_the_alert_count_and_the_pause():
    tip = tray_state.tooltip(2, ["TSN 2", "Sky"], "Notifications paused")
    assert "Playing TSN 2 (+1)" in tip and "2 alerts in the next 12 hours" in tip
    assert tip.endswith("Notifications paused")
    assert tray_state.tooltip(0, [], "") == "StreamSelect"


# ── the one seam senders go through ─────────────────────────────────────────

def test_only_alerts_reach_the_system_sink(qapp):
    mgr = NotificationManager()
    seen = []
    mgr.system_sink = seen.append
    mgr.show(title="Refreshing", message="…")
    mgr.show(title="Starting now", message="A vs B", alert="game", open_target="view:sports")
    assert [(n.title, n.alert, n.open_target) for n in seen] == [("Starting now", "game", "view:sports")]
    assert len(mgr.notifications) == 2, "the in-app toast is still shown"


def test_alerted_items_keep_only_matching_games_that_are_not_over():
    def game(a, b, minutes):
        return SimpleNamespace(team_a=a, team_b=b, sport="unlisted-sport", league="NHL",
                               start_utc=NOW + timedelta(minutes=minutes), matchup=f"{a} vs {b}")
    alert = SimpleNamespace(matches=lambda g: "Kraken" in (g.team_a, g.team_b))
    got = alerted_items([game("Kraken", "Jets", 60), game("Oilers", "Jets", 60),
                         game("Kraken", "Stars", -600)], [alert], NOW)
    assert [(i.title, i.target, i.kind) for i in got] == [
        ("Kraken vs Jets", "view:sports", tray_state.KIND_GAME)]


def test_a_live_alerted_game_carries_its_preferred_feed_and_an_upcoming_one_none():
    from dataclasses import replace
    from streamselect.core.games.read import GameDTO, GameFeedDTO

    feeds = (GameFeedDTO("ch-first", "One", "Pack A", False), GameFeedDTO("ch-pref", "Two", "Pack B", False))

    def game(gid, a, minutes):
        return GameDTO(gid, "hockey", "NHL", a, "Jets", NOW + timedelta(minutes=minutes), 1, False, 2, feeds)
    alert = SimpleNamespace(matches=lambda g: True)
    preferred_first = lambda g: replace(g, feeds=tuple(reversed(g.feeds)))  # noqa: E731
    got = alerted_items([game(1, "Kraken", -20), game(2, "Oilers", 90)], [alert], NOW, preferred_first)
    by = {i.title.split()[0]: i for i in got}
    assert by["Kraken"].live and by["Kraken"].plays == "ch-pref", "the card's first feed: the preferred one"
    assert not by["Oilers"].live and by["Oilers"].plays is None, "a future game only opens the app"


# ── the controller ──────────────────────────────────────────────────────────

class _Host(QWidget):
    def __init__(self, config, playing=None, games=()):
        super().__init__()
        self.config = config
        self.stopped = []
        self.player_manager = SimpleNamespace(playing_titles=lambda: dict(playing or {}),
                                              stop=lambda key: self.stopped.append(key))
        self.event_alert_notifier = _Notifier(games)
        self.shown_on = []
        self.played = []

    def play_channel_by_id(self, channel_id):
        self.played.append(channel_id)

    def _run_query(self, *a, **k):
        pass

    def show_from_tray(self, target=None):
        self.shown_on.append(target)

    def toggle_from_tray(self):
        pass

    def quit_app(self):
        pass

    def _manual_update_check(self):
        pass


class _Notifier(QObject):
    """The event-alert notifier's face to the tray: its games and its poll signal."""

    updated = pyqtSignal()

    def __init__(self, games):
        super().__init__()
        self.upcoming = list(games)


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setattr(tray_mod.watchlist, "rules", lambda _c: ())
    cfg = settings_config_double(config_dir=tmp_path)
    cfg.tray_close_to_tray = True
    return cfg


def _texts(menu):
    return [a.text() for a in menu.actions()]


def test_menu_shows_what_plays_stop_and_the_alerts(qapp, config):
    host = _Host(config, playing={"main": "TSN 2"}, games=[_item("Kraken vs Jets", 30)])
    ctl = tray_mod.TrayController(host, clock=lambda: NOW)
    ctl.rebuild()
    texts = _texts(ctl._menu)
    assert "TSN 2" in texts and "Stop playback" in texts
    assert any("Kraken vs Jets" in t for t in texts)
    assert texts[-1] == "Quit StreamSelect"
    ctl.stop_playback()
    assert host.stopped == ["main"]
    alert = next(a for a in ctl._menu.actions() if "Kraken" in a.text())
    alert.trigger()
    assert host.shown_on == ["view:sports"]
    ctl.shutdown()
    destroy_widget(ctl._menu, host)


def test_a_live_item_opens_the_app_and_plays_an_upcoming_one_only_opens(qapp, config):
    live = TrayItem(NOW - timedelta(minutes=20), "Kraken vs Jets", "NHL", "view:sports",
                    live=True, channel_id="ch-pref")
    later = TrayItem(NOW + timedelta(minutes=90), "News at Six", "", "view:epg", channel_id="ch-news")
    host = _Host(config, games=[live, later])
    ctl = tray_mod.TrayController(host, clock=lambda: NOW)
    ctl.rebuild()
    by = {a.text(): a for a in ctl._menu.actions()}
    next(a for t, a in by.items() if "Kraken" in t).trigger()
    assert host.shown_on == ["view:sports"] and host.played == ["ch-pref"]
    next(a for t, a in by.items() if "News at Six" in t).trigger()
    assert host.shown_on[-1] == "view:epg" and host.played == ["ch-pref"], "nothing new plays"
    ctl.shutdown()
    destroy_widget(ctl._menu, host)


def _icon_image(action):
    return action.icon().pixmap(16, 16).toImage()


def test_the_menu_heads_sports_alerts_above_watch_alerts_and_marks_games_apart(qapp, config):
    host = _Host(config, games=[_show("Sitcom", -10, live=True), _show("News", 60),
                                _game("Kraken vs Jets", 35)])
    ctl = tray_mod.TrayController(host, clock=lambda: NOW)
    ctl.rebuild()
    acts = ctl._menu.actions()
    texts = [a.text() for a in acts]
    sports, watch = texts.index("Sports alerts"), texts.index("Watch Alerts")
    game = next(i for i, t in enumerate(texts) if "Kraken" in t)
    shows = [i for i, t in enumerate(texts) if "Sitcom" in t or "News" in t]
    assert acts[sports].isSeparator() and acts[watch].isSeparator()
    assert sports < game < watch < min(shows)
    upcoming_show = next(acts[i] for i in shows if "News" in texts[i])
    assert _icon_image(acts[game]) != _icon_image(upcoming_show), "a game looks unlike a guide match"
    assert "3 alerts" in ctl._icon.toolTip()
    ctl.shutdown()
    destroy_widget(ctl._menu, host)


def test_menu_says_when_nothing_is_alerted(qapp, config):
    host = _Host(config)
    ctl = tray_mod.TrayController(host, clock=lambda: NOW)
    ctl.rebuild()
    texts = _texts(ctl._menu)
    assert "Nothing alerted in the next 12 hours" in texts
    assert "Stop playback" not in texts
    ctl.shutdown()
    destroy_widget(ctl._menu, host)


def test_notifications_go_out_only_hidden_switched_on_and_unpaused(qapp, config):
    host = _Host(config)
    ctl = tray_mod.TrayController(host, clock=lambda: NOW)
    ctl.set_visible(True)
    assert ctl.wants("game"), "window hidden, games on, not paused"
    host.show()
    assert not ctl.wants("game"), "the window is open: the in-app toast is enough (TQ5)"
    host.hide()
    config.tray_notify_games = False
    assert not ctl.wants("game") and ctl.wants("watch")
    ctl.set_pause(tray_state.PAUSE_HOUR)
    assert not ctl.wants("watch")
    ctl.set_pause("")
    assert ctl.wants("watch")
    assert not ctl.wants("")
    ctl.set_visible(False)
    assert not ctl.wants("watch"), "no icon, no system notifications"
    ctl.shutdown()
    destroy_widget(ctl._menu, host)


def _blue_icon():
    pm = QPixmap(64, 64)
    pm.fill(QColor(0, 0, 255))
    return QIcon(pm)


def _near(a: QColor, b: QColor, tol=30) -> bool:
    return all(abs(x - y) < tol for x, y in ((a.red(), b.red()), (a.green(), b.green()),
                                               (a.blue(), b.blue())))


_CORNER = [b for b in tray_mod._BADGES if b != tray_state.BADGE_LIVE]


def _disc_colour(badge, img):
    """A pixel on the badge's disc, clear of its glyph (64 px icon)."""
    return img.pixelColor(32, 5) if badge == tray_state.BADGE_LIVE else img.pixelColor(61, 46)


def _icon_for(badge):
    glyph, token = tray_mod._BADGES[badge]
    icon = (tray_mod.live_icon(glyph, token) if badge == tray_state.BADGE_LIVE
            else tray_mod.badged_icon(_blue_icon(), glyph, token))
    return icon.pixmap(64, 64).toImage()


@pytest.mark.parametrize("badge", _CORNER)
def test_each_corner_badge_keeps_the_app_icon_and_adds_a_cut_out_disc(qapp, badge):
    from streamselect.gui import theme
    glyph, token = tray_mod._BADGES[badge]
    img = _icon_for(badge)
    assert img.pixelColor(8, 8) == QColor(0, 0, 255), "the app icon still shows"
    edge = _disc_colour(badge, img)
    assert _near(edge, QColor(getattr(theme, token))), f"a {token} disc, bottom-right"
    centre = img.pixelColor(64 - 22, 64 - 22)
    assert centre != edge, "the disc carries a mark, not a plain dot"
    d = round(64 * tray_mod.BADGE_SHARE)
    gap = img.pixelColor(64 - d // 2, 64 - d - 2)    # just above the disc, inside the logo
    assert gap.alpha() == 0, "a clear ring cuts the badge out of the logo"


def test_the_corner_badge_is_big_enough_to_read_at_tray_size(qapp):
    """Owner, 2026-11-17: "should the notification alert be so small". At 22 px
    it was a 12 px disc; it is now two-thirds of the icon."""
    img = tray_mod.badged_icon(_blue_icon(), "tray_alert_badge", "COLOR_TRAY_ALERT") \
        .pixmap(22, 22).toImage()
    from streamselect.gui import theme
    fill = QColor(theme.COLOR_TRAY_ALERT)
    widest = 0
    for y in range(22):
        xs = [x for x in range(22) if _near(img.pixelColor(x, y), fill, tol=60)]
        widest = max(widest, max(xs) - min(xs) + 1 if xs else 0)
    assert widest >= 14, f"disc {widest} px wide at 22 px (was 12)"


def test_a_live_game_replaces_the_whole_icon_with_a_full_disc(qapp):
    from streamselect.gui import theme
    img = _icon_for(tray_state.BADGE_LIVE)
    fill = QColor(theme.COLOR_TRAY_LIVE)
    assert _near(img.pixelColor(32, 5), fill) and _near(img.pixelColor(5, 32), fill), \
        "the disc spans the icon"
    assert img.pixelColor(32, 32) != img.pixelColor(32, 5), "with its glyph in the middle"
    blue = QColor(0, 0, 255)
    assert not any(_near(img.pixelColor(x, y), blue, tol=40)
                   for x in range(0, 64, 4) for y in range(0, 64, 4)), "no small logo to squint at"


def test_the_three_states_look_different_and_none_is_red(qapp):
    colours = [_disc_colour(b, _icon_for(b)) for b in tray_mod._BADGES]
    assert len({c.name() for c in colours}) == 3
    assert all(not _near(c, QColor(229, 57, 53), tol=60) for c in colours), \
        "the red alarm disc is retired (owner, 2026-11-16)"


def test_badge_order_live_game_then_alert_then_update_alone():
    K = tray_state
    assert K.badge_for(False, set()) is None
    assert K.badge_for(False, {K.KIND_UPDATE}) == K.BADGE_UPDATE
    assert K.badge_for(False, {K.KIND_UPDATE, K.KIND_WATCH}) == K.BADGE_ALERT
    assert K.badge_for(False, {K.KIND_GAME}) == K.BADGE_ALERT
    assert K.badge_for(True, {K.KIND_WATCH}) == K.BADGE_LIVE
    assert K.badge_for(True, set()) == K.BADGE_LIVE


def test_the_icon_follows_alerts_updates_and_a_live_game(qapp, config):
    old = qapp.windowIcon()
    qapp.setWindowIcon(_blue_icon())
    host = _Host(config)
    ctl = tray_mod.TrayController(host, clock=lambda: NOW)
    try:
        def probe(img):
            return img.pixelColor(61, 46).name(), img.pixelColor(32, 5).name()

        def badge():
            return probe(ctl._icon.icon().pixmap(64, 64).toImage())
        disc = {b: probe(_icon_for(b)) for b in tray_mod._BADGES}
        plain = badge()
        ctl.message("Still running", "…")
        assert not ctl.unseen and badge() == plain, "the hide notice is not an alert"
        ctl.message("Update", "1.0.6 is out", alert=tray_state.KIND_UPDATE)
        assert badge() == disc[tray_state.BADGE_UPDATE]
        ctl.message("Starting soon", "A show", "view:epg", alert=tray_state.KIND_WATCH)
        assert badge() == disc[tray_state.BADGE_ALERT], "an alert outranks the update"
        ctl._menu.aboutToShow.emit()
        assert not ctl.unseen and badge() == plain

        host.event_alert_notifier.upcoming = [_game("Kraken vs Jets", -10, live=True)]
        host.event_alert_notifier.updated.emit()
        assert badge() == disc[tray_state.BADGE_LIVE], "a poll finding the game on badges at once"
        ctl._menu.aboutToShow.emit()
        assert badge() == disc[tray_state.BADGE_LIVE], "seen or not, it stays while the game is on"
        host.event_alert_notifier.upcoming = []
        host.event_alert_notifier.updated.emit()
        assert badge() == plain
    finally:
        ctl.shutdown()
        qapp.setWindowIcon(old)
        destroy_widget(ctl._menu, host)


# ── close, hide, quit ───────────────────────────────────────────────────────

class _Window(main_window_tray._TrayMixin, QWidget):
    def __init__(self, config, tray):
        super().__init__()
        self.config = config
        self.tray = tray
        self.navigated = []

    def navigate_to(self, target):
        self.navigated.append(target)
        return True


class _View(QWidget):
    """A content view with a lifecycle: what timers a hidden window must pause."""

    def __init__(self, parent):
        super().__init__(parent)
        self.calls = []

    def on_activate(self):
        self.calls.append("activate")

    def on_deactivate(self):
        self.calls.append("deactivate")


class _Close:
    def __init__(self, spontaneous):
        self._s = spontaneous
        self.ignored = False

    def spontaneous(self):
        return self._s

    def ignore(self):
        self.ignored = True


def _window(config):
    tray = SimpleNamespace(messages=[], rebuild=lambda: None, set_visible=lambda v: None,
                           mark_seen=lambda: None)
    tray.message = lambda *a: tray.messages.append(a)
    return _Window(config, tray)


def test_a_close_from_code_quits_even_with_the_tray_on(qapp, config):
    w = _window(config)
    assert w._close_to_tray(_Close(spontaneous=False)) is False
    destroy_widget(w)


def test_the_users_close_hides_to_the_tray_and_says_so_once(qapp, config):
    w = _window(config)
    w.show()
    event = _Close(spontaneous=True)
    assert w._close_to_tray(event) is True and event.ignored
    assert not w.isVisible()
    assert len(w.tray.messages) == 1 and config.tray_hide_notice_shown
    w.show()
    w._close_to_tray(_Close(spontaneous=True))
    assert len(w.tray.messages) == 1, "the notice is shown once"
    w.show_from_tray("view:sports")
    assert w.isVisible() and w.navigated == ["view:sports"]
    destroy_widget(w)


def test_hiding_to_the_tray_pauses_the_view_on_screen_and_showing_resumes_it(qapp, config):
    w = _window(config)
    w.epg_view = _View(w)
    w.discover_view = _View(w)
    w.discover_view.setVisible(False)              # not the view on screen
    w.show()
    w.hide_to_tray()
    assert w.epg_view.calls == ["deactivate"] and w.discover_view.calls == []
    w.show_from_tray()
    assert w.epg_view.calls == ["deactivate", "activate"]
    w.hide_to_tray()
    w.show_from_tray("view:sports")
    assert w.epg_view.calls[-1] == "deactivate", "navigating activates its own view instead"
    destroy_widget(w)


def test_the_guide_timer_refreshes_only_the_tab_on_screen():
    from streamselect.gui.epg_view import EpgView
    for tab, reloads in ((3, 1), (0, 0), (1, 0), (2, 0), (4, 0)):
        seen = []
        host = SimpleNamespace(tab_bar=SimpleNamespace(currentIndex=lambda t=tab: t),
                               _reload_on_now=lambda: seen.append("on_now"),
                               _render_events=lambda _c: None, _events_dto_cache=[])
        EpgView._on_live_timer_tick(host)
        assert len(seen) == reloads, f"tab {tab}: On Now is re-read only while it shows"


@pytest.mark.parametrize("answer, hides, stored", [(True, True, True), (False, False, False),
                                                    (None, True, None)])
def test_the_first_close_asks_once(qapp, config, monkeypatch, answer, hides, stored):
    config.tray_close_to_tray = None
    w = _window(config)
    monkeypatch.setattr(main_window_tray._TrayMixin, "_ask_close_to_tray", lambda self: answer)
    w.show()
    event = _Close(spontaneous=True)
    assert w._close_to_tray(event) is hides
    assert config.tray_close_to_tray is stored
    if answer is None:
        assert event.ignored and w.isVisible(), "dismissing the question keeps the window open"
    QApplication.instance().setQuitOnLastWindowClosed(True)
    destroy_widget(w)


def test_no_tray_means_close_quits(qapp, config):
    w = _window(config)
    w.tray = None
    assert w._close_to_tray(_Close(spontaneous=True)) is False
    destroy_widget(w)


# ── Settings ▸ System Tray ──────────────────────────────────────────────────

def test_settings_page_round_trips(qapp, tmp_path, monkeypatch):
    from streamselect.gui import settings_tray_tab
    from streamselect.gui.settings_dialog import SettingsDialog, _SECTION_HELP
    monkeypatch.setattr(settings_tray_tab, "tray_available", lambda: True)
    cfg = settings_config_double(config_dir=tmp_path)
    assert cfg.tray_close_to_tray is None and _SECTION_HELP["tray"].strip()
    dlg = SettingsDialog(cfg, parent=None)
    try:
        dlg._save_values()
        assert cfg.tray_close_to_tray is None, "an untouched page keeps 'never asked' (TQ1)"
        dlg._tray_close_check.setChecked(True)
        dlg._tray_notify_games_check.setChecked(False)
        dlg._save_values()
        assert cfg.tray_close_to_tray is True and cfg.tray_notify_games is False
    finally:
        destroy_widget(dlg)


def test_settings_page_without_a_tray_greys_out_and_says_why(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QLabel
    from streamselect.gui import settings_tray_tab

    monkeypatch.setattr(settings_tray_tab, "tray_available", lambda: False)
    host = settings_tray_tab.SettingsTrayTabMixin()
    page = host._build_tray_tab()
    page.resize(560, 400)
    page.show()
    qapp.processEvents()
    try:
        assert not host._tray_close_check.isEnabled()
        note = next(lb for lb in page.findChildren(QLabel) if lb.text() == settings_tray_tab.NO_TRAY_TEXT)
        assert note.isVisible() and note.width() > 0 and note.height() > 0
        check = host._tray_close_check
        below = note.mapTo(page, note.rect().topLeft()).y()
        assert below >= check.mapTo(page, check.rect().bottomLeft()).y(), \
            "the reason sits under the greyed-out setting"
    finally:
        destroy_widget(page)
