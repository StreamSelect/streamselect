"""System tray ("Tray Mode" design, TQ1-TQ14): what it lists, when it notifies,
what a close does, and the Settings page."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
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
    assert [(i.title, i.target) for i in got] == [("Kraken vs Jets", "view:sports")]


# ── the controller ──────────────────────────────────────────────────────────

class _Host(QWidget):
    def __init__(self, config, playing=None, games=()):
        super().__init__()
        self.config = config
        self.stopped = []
        self.player_manager = SimpleNamespace(playing_titles=lambda: dict(playing or {}),
                                              stop=lambda key: self.stopped.append(key))
        self.event_alert_notifier = SimpleNamespace(upcoming=list(games))
        self.shown_on = []

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


# ── close, hide, quit ───────────────────────────────────────────────────────

class _Window(main_window_tray._TrayMixin, QWidget):
    def __init__(self, config, tray):
        super().__init__()
        self.config = config
        self.tray = tray
        self.navigated = []

    def navigate_to(self, target):
        self.navigated.append(target)


class _Close:
    def __init__(self, spontaneous):
        self._s = spontaneous
        self.ignored = False

    def spontaneous(self):
        return self._s

    def ignore(self):
        self.ignored = True


def _window(config):
    tray = SimpleNamespace(messages=[], rebuild=lambda: None, set_visible=lambda v: None)
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
