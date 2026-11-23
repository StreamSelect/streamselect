"""Subtitles off on live channels, and the one set of per-stream options behind it.

Live captions are typed as a broadcast airs, so they lag and garble (owner,
2026-11-22). One sticky setting, shown in the playback menu and in Settings →
Playback, starts live channels with no subtitle track. Movies and series keep theirs.

Every way ``MPVPlayer.play`` can start a stream takes the same per-stream options:
loading into a running window, relaunching it for a buffer mode, or falling back to
a standalone process. Three of those fallbacks once dropped the resume point.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from streamselect.core.players import mpv as mpv_mod
from streamselect.core.players.mpv import MPVPlayer


@dataclass
class _Config:
    default_cache_size: str = "auto"
    mpv_extra_args: list = field(default_factory=list)
    player_mode: str = "single-instance"
    close_player_when_finished: bool = False
    buffer_profile: str = "modest"
    prebuffer_before_play: bool = False
    prebuffer_wait_secs: int = 10
    mpv_args_override_all: bool = False
    live_subtitles_off: bool = True


def _spawned_command(player: MPVPlayer, **play_kwargs) -> list[str]:
    """Play through a standalone process and return the command line it ran."""
    with patch.object(mpv_mod.subprocess, "Popen") as popen, \
         patch.object(mpv_mod, "start_log_tap"), \
         patch.object(mpv_mod, "_resolve_mpv_binary", return_value="mpv"):
        assert player.play("http://x/s", "T", **play_kwargs) is True
    return popen.call_args.args[0]


def _loadfile(player: MPVPlayer, **play_kwargs) -> list:
    """Play into a running window and return the loadfile command it sent."""
    sent = []
    with patch.object(player, "_ensure_instance_running", return_value=True), \
         patch.object(player, "_relaunch_instance", return_value=True), \
         patch.object(player, "_send_ipc_command",
                      side_effect=lambda cmd, key, **_: sent.append(cmd["command"]) or True):
        assert player.play("http://x/s", "T", **play_kwargs) is True
    return next(c for c in sent if c[0] == "loadfile")


# ── the resume point survives every route ──────────────────────────────────

def test_a_new_window_per_play_resumes_where_you_left_off():
    cmd = _spawned_command(MPVPlayer(_Config(player_mode="multiple-instances")),
                           start_seconds=754)
    assert "--start=754" in cmd


@pytest.mark.parametrize("failure", ["window_will_not_start", "window_will_not_answer"])
def test_falling_back_to_a_standalone_player_keeps_the_resume_point(failure):
    player = MPVPlayer(_Config())
    with patch.object(player, "_ensure_instance_running",
                      return_value=failure != "window_will_not_start"), \
         patch.object(player, "_send_ipc_command", return_value=False):
        cmd = _spawned_command(player, start_seconds=754)
    assert "--start=754" in cmd


# ── subtitles off: live only, every route ──────────────────────────────────

def test_a_live_channel_loads_with_no_subtitle_track():
    assert _loadfile(MPVPlayer(_Config()), live=True) == [
        "loadfile", "http://x/s", "replace", 0, "sid=no"]


def test_resume_and_subtitles_off_go_together():
    assert _loadfile(MPVPlayer(_Config()), live=True, start_seconds=30)[4] == "start=30,sid=no"


@pytest.mark.parametrize("live,setting", [(False, True), (True, False)])
def test_subtitles_stay_when_not_live_or_when_the_setting_is_off(live, setting):
    assert _loadfile(MPVPlayer(_Config(live_subtitles_off=setting)), live=live) == [
        "loadfile", "http://x/s", "replace"]


def test_a_live_channel_in_its_own_window_starts_with_no_subtitles():
    cmd = _spawned_command(MPVPlayer(_Config(player_mode="multiple-instances")), live=True)
    assert "--sid=no" in cmd and cmd[-1] == "http://x/s"


def test_a_buffer_mode_relaunch_keeps_subtitles_off():
    assert _loadfile(MPVPlayer(_Config()), live=True, open_ended_buffer=True)[4] == "sid=no"


# ── the play chokepoint says whether it is live ────────────────────────────

def test_the_app_marks_only_live_channels_as_live(tmp_path):
    from streamselect.core.database import ChannelDB, Database, ProviderDB
    from streamselect.gui.main_window_streaming import _StreamingMixin

    db = Database(f"sqlite:///{tmp_path / 't.db'}")
    db.create_tables()
    with db.session_scope() as session:
        session.add(ProviderDB(id="p1", name="One source", type="xtream", url="http://example.com",
                               username="u", password="p"))
        session.add(ChannelDB(id="live1", source_id="1", provider_id="p1", name="Game", media_type="live",
                              stream_url="http://example.com/1"))
        session.add(ChannelDB(id="vod1", source_id="2", provider_id="p1", name="Film", media_type="movie",
                              stream_url="http://example.com/2"))
    host = SimpleNamespace(db=db)
    is_live = _StreamingMixin._channel_is_live
    assert is_live(host, "live1") is True
    assert is_live(host, "vod1") is False
    assert is_live(host, "") is False
    db.close()


def test_play_checked_passes_live_to_the_player():
    from streamselect.gui.main_window_streaming import _StreamingMixin

    host = MagicMock()
    host.player_manager.check_capacity.return_value = None
    host._channel_is_live.side_effect = lambda cid: cid == "live1"
    _StreamingMixin._play_checked(host, "http://x/s", "Game", provider_id="p1", channel_id="live1")
    assert host.player_manager.play.call_args.kwargs["live"] is True


# ── the switch: one setting, in the menu and in Settings ──────────────────

def test_the_menu_toggle_is_sticky_and_matches_settings(qtbot, monkeypatch):
    from PyQt6.QtWidgets import QWidget

    from streamselect.gui import deferred_config_save, playback_menu
    from streamselect.gui.settings_player_rows import LIVE_SUBTITLES_LABEL

    save = MagicMock()
    monkeypatch.setattr(deferred_config_save, "save_soon", save)
    host = QWidget()
    qtbot.addWidget(host)
    host.config = SimpleNamespace(normalize_volume=False, audio_downmix="auto",
                                  video_decoder="auto", mpv_args_override_all=True,
                                  live_subtitles_off=False)
    host.player_manager = MagicMock()
    host.player_manager.active_keys.return_value = []
    host._apply_player_settings = MagicMock()
    host.status = MagicMock()
    menu = playback_menu.build_playback_menu(host)
    toggle = next(a for a in menu.actions() if a.text() == LIVE_SUBTITLES_LABEL)
    assert toggle.isCheckable() and not toggle.isChecked()
    assert toggle.isEnabled(), "Override all is about mpv arguments, not this"
    assert menu.actionGeometry(toggle).height() > 0
    toggle.trigger()
    assert host.config.live_subtitles_off is True
    save.assert_called_once_with(host)
    again = playback_menu.build_playback_menu(host)
    assert next(a for a in again.actions() if a.text() == LIVE_SUBTITLES_LABEL).isChecked()


def test_settings_shows_and_saves_the_same_setting(qtbot):
    from streamselect.core.config import Config
    from streamselect.gui.settings_dialog import SettingsDialog
    from tests.conftest import destroy_widget

    config = Config()
    config.live_subtitles_off = True
    dlg = SettingsDialog(config)
    try:
        check = dlg._live_subtitles_off_check
        assert check.isChecked()
        assert check.isVisibleTo(dlg._nav.page(next(
            i for i in range(dlg._nav.count()) if dlg._nav.label(i) == "Playback")))
        assert check.toolTip()                 # explained in the help column
        check.setChecked(False)
        dlg._save_values()
        assert config.live_subtitles_off is False
    finally:
        destroy_widget(dlg)
