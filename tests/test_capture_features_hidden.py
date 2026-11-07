"""Downloading and recording stay out of sight until STREAMSELECT_DEV is set."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from streamselect.core import feature_gates


@pytest.fixture
def hidden(monkeypatch):
    monkeypatch.setattr(feature_gates, "capture_enabled", lambda: False)


def test_the_switch_follows_dev_mode(monkeypatch):
    monkeypatch.undo()
    monkeypatch.delenv("STREAMSELECT_DEV", raising=False)
    assert feature_gates.capture_enabled() is False
    monkeypatch.setenv("STREAMSELECT_DEV", "1")
    assert feature_gates.capture_enabled() is True


@pytest.mark.parametrize("action_id,media_type", [("download", "movie"), ("record", "live"),
                                                  ("record_window", "live")])
def test_the_menu_entries_show_only_when_offered(monkeypatch, action_id, media_type):
    from streamselect.gui.channel_menu import ACTIONS, ChannelMenuContext

    ctx = ChannelMenuContext(channel_ids=["c"], surface="channel", media_type=media_type,
                             channel_found=True)
    assert ACTIONS[action_id].applies(ctx)
    monkeypatch.setattr(feature_gates, "capture_enabled", lambda: False)
    assert not ACTIONS[action_id].applies(ctx)


def test_the_sidebar_builds_neither_section(hidden):
    from streamselect.gui.main_window import MainWindow

    host = MainWindow.__new__(MainWindow)
    assert MainWindow.create_section(host, "downloads") is None
    assert MainWindow.create_section(host, "recordings") is None


def test_a_saved_downloaded_scope_comes_back_as_all(hidden):
    from streamselect.gui import downloaded_scope

    state = {"list_scope": "downloaded", "downloaded_mode": True, "hidden_mode": False}
    assert downloaded_scope.scope_from_state(state) == ("all", False, False)


def test_the_downloaded_tab_is_not_shown(qtbot, hidden):
    from PyQt6.QtWidgets import QPushButton, QWidget

    from streamselect.gui import downloaded_scope

    holder = QWidget()
    qtbot.addWidget(holder)
    buttons = {name: QPushButton(name, holder)
               for name in ("_tab_all_btn", "_tab_downloaded_btn", "_tab_hidden_btn")}
    holder.show()
    downloaded_scope.sync_scope_buttons(SimpleNamespace(**buttons), "all", False, False)
    assert not buttons["_tab_downloaded_btn"].isVisible()
    assert buttons["_tab_all_btn"].isVisible() and buttons["_tab_hidden_btn"].isVisible()


def test_settings_leaves_out_both_pages_but_still_saves_their_values(qapp, hidden):
    from streamselect.gui.settings_dialog import SettingsDialog
    from tests.test_settings_tab_layout import _FakeConfig

    cfg = _FakeConfig()
    dlg = SettingsDialog(cfg, parent=None)
    listed = list(dlg._nav._section_ids)
    assert "downloads" not in listed and "recording" not in listed
    assert "playback" in listed
    assert dlg._download_dir_input.text() is not None  # still built, loaded and saved
    dlg.close()


def test_the_sidebar_list_hides_both_and_saving_keeps_their_place(qapp, hidden):
    from PyQt6.QtCore import Qt

    from tests.test_settings_tab_layout import _FakeConfig, _full_dialog

    dlg = _full_dialog(qapp)
    cfg = _FakeConfig()
    cfg.sidebar_sections = ["alerts", "downloads", "queue", "recordings", "favorites"]
    cfg.sidebar_visible_sections = ["alerts", "downloads", "queue", "favorites"]
    dlg.config = cfg
    dlg._load_values()
    shown = [dlg._sidebar_list.item(i).data(Qt.ItemDataRole.UserRole)
             for i in range(dlg._sidebar_list.count())]
    assert "downloads" not in shown and "recordings" not in shown

    dlg._save_values()
    assert cfg.sidebar_sections[:5] == ["alerts", "downloads", "queue", "recordings", "favorites"]
    assert "downloads" in cfg.sidebar_visible_sections
    assert "recordings" not in cfg.sidebar_visible_sections
