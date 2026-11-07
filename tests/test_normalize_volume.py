"""Player settings: they reach new windows, open windows and the screen."""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from PyQt6.QtWidgets import QApplication, QFormLayout, QWidget

from streamselect.core.player_manager import PlayerManager
from streamselect.core.players.mpv import MPVPlayer
from streamselect.core.players.mpv_args import normalize_active, normalize_command
from streamselect.gui import settings_apply
from streamselect.gui.settings_player_rows import add_player_rows


@dataclass
class _Config:
    normalize_volume: bool = False
    audio_downmix: str = "auto"
    video_decoder: str = "auto"
    mpv_args_override_all: bool = False
    mpv_extra_args: list = field(default_factory=list)
    default_cache_size: str = "auto"
    buffer_profile: str = "modest"
    player_mode: str = "single-instance"
    close_player_when_finished: bool = False
    prebuffer_before_play: bool = False
    prebuffer_wait_secs: int = 10


def _flags(args: list[str]) -> list[str]:
    return [a for a in args if a.startswith("--af-add=") and "dynaudnorm" in a]


@pytest.mark.parametrize("compose", [
    lambda p: p._compose_extra_args(),
    lambda p: p._compose_open_ended_buffer_args(),
    lambda p: p._compose_deep_cache_args("/tmp/x.ts"),
])
def test_every_launch_path_carries_the_filter_only_when_on(compose):
    assert len(_flags(compose(MPVPlayer(_Config(normalize_volume=True))))) == 1
    assert _flags(compose(MPVPlayer(_Config(normalize_volume=False)))) == []
    assert _flags(compose(MPVPlayer(_Config(normalize_volume=True,
                                            mpv_args_override_all=True)))) == []


def test_user_flags_still_come_after_the_filter():
    args = MPVPlayer(_Config(normalize_volume=True,
                             mpv_extra_args=["--af=lavfi=[mine]"]))._compose_extra_args()
    assert args.index(_flags(args)[0]) < args.index("--af=lavfi=[mine]")


class _Player:
    """Stands in for mpv's per-window ``af`` state and applies the real commands."""

    def __init__(self, windows: dict[str, list]):
        self.windows = windows
        self.channels = dict.fromkeys(windows, "auto-safe")
        self.hwdec = dict.fromkeys(windows, ["vaapi"])
        self.sent: list = []

    def active_keys(self):
        return list(self.windows)

    def get_properties(self, names, key=None):
        return {"af": self.windows[key], "audio-channels": self.channels[key],
                "hwdec": self.hwdec[key]}

    def send_command(self, cmd, key=None):
        self.sent.append((key, cmd))
        if cmd[:2] == ["set_property", "hwdec"]:
            self.hwdec[key] = [cmd[2]]
            return True
        if cmd[0] == "set_property":
            self.channels[key] = cmd[2]
            return True
        self.windows[key] = ([{"label": "streamselect-normalize"}] if cmd[1] == "add" else [])
        return True


def _manager(config, windows) -> PlayerManager:
    manager = PlayerManager.__new__(PlayerManager)
    manager.config = config
    manager._software_decoding = False
    manager.player = _Player(windows)
    return manager


def test_turning_it_on_reaches_every_open_window():
    manager = _manager(_Config(normalize_volume=True), {"a": [], "b": []})
    assert manager.sync_player_settings() == 2
    assert all(normalize_active(af) for af in manager.player.windows.values())


def test_turning_it_off_removes_it_from_an_open_window():
    manager = _manager(_Config(), {"a": [{"label": "streamselect-normalize"}]})
    assert manager.sync_player_settings() == 1
    assert manager.player.sent == [("a", normalize_command(False))]
    assert manager.player.windows["a"] == []


def test_a_window_already_right_is_left_alone():
    """Re-adding the filter would restart its loudness measurement on every OK."""
    manager = _manager(_Config(normalize_volume=True), {"a": [{"label": "streamselect-normalize"}]})
    assert manager.sync_player_settings() == 0
    assert manager.player.sent == []


def test_override_all_turns_it_off_in_open_windows_too():
    manager = _manager(_Config(normalize_volume=True, mpv_args_override_all=True),
                       {"a": [{"label": "streamselect-normalize"}]})
    manager.sync_player_settings()
    assert manager.player.windows["a"] == []


@pytest.mark.parametrize("setting,flag", [("stereo", "--audio-channels=stereo"),
                                          ("mono", "--audio-channels=mono")])
def test_downmix_is_on_the_launch_command(setting, flag):
    assert flag in MPVPlayer(_Config(audio_downmix=setting))._compose_extra_args()


def test_downmix_off_adds_no_flag():
    args = MPVPlayer(_Config())._compose_extra_args()
    assert not [a for a in args if a.startswith("--audio-channels")]


def test_downmix_reaches_an_open_window_and_can_be_turned_back_off():
    config = _Config(audio_downmix="mono")
    manager = _manager(config, {"a": []})
    assert manager.sync_player_settings() == 1
    assert manager.player.channels["a"] == "mono"
    config.audio_downmix = "auto"
    assert manager.sync_player_settings() == 1
    assert manager.player.channels["a"] == "auto-safe"
    assert manager.sync_player_settings() == 0


def test_software_decoder_is_on_the_launch_command_only_when_chosen():
    assert "--hwdec=no" in MPVPlayer(_Config(video_decoder="software"))._compose_extra_args()
    assert not [a for a in MPVPlayer(_Config())._compose_extra_args() if "hwdec" in a]


def test_decoder_switches_an_open_window_both_ways():
    config = _Config(video_decoder="software")
    manager = _manager(config, {"a": []})
    assert manager.sync_player_settings() == 1
    assert manager.player.hwdec["a"] == ["no"]
    config.video_decoder = "auto"
    assert manager.sync_player_settings() == 1
    assert manager.player.hwdec["a"] == ["auto-safe"]


@pytest.mark.parametrize("own_hwdec", [["vaapi"], ["no"]])
def test_changing_the_sound_leaves_the_windows_own_decoder_alone(own_hwdec):
    """mpv's default is "no", and a user's mpv.conf can say anything: Automatic
    must not read either as something to correct, or the picture skips."""
    config = _Config()
    manager = _manager(config, {"a": []})
    manager.player.hwdec["a"] = own_hwdec
    config.normalize_volume = True
    assert manager.sync_player_settings() == 1
    assert manager.player.hwdec["a"] == own_hwdec
    assert [c for _k, c in manager.player.sent if "hwdec" in c] == []


def test_settings_ok_runs_the_live_apply():
    assert "_apply_player_settings" in settings_apply.HANDLERS


def test_the_rows_render_in_order_and_nothing_is_squeezed(qtbot):
    """474px is the width the Playback page really gets inside the dialog. A combo
    narrower than its content clips its own text, which no ordering check would see."""
    host = QWidget()
    qtbot.addWidget(host)
    form = QFormLayout(host)
    dlg = QWidget()
    qtbot.addWidget(dlg)
    add_player_rows(dlg, form)
    host.resize(474, 300)
    host.show()
    QApplication.processEvents()
    check = dlg._normalize_volume_check
    downmix, decoder, buffering = (dlg._audio_downmix_combo, dlg._video_decoder_combo,
                                   dlg._buffer_combo)
    assert check.text() == "Normalize volume"
    assert check.toolTip()
    assert [downmix.itemData(i) for i in range(downmix.count())] == ["auto", "stereo", "mono"]
    assert check.geometry().bottom() <= downmix.geometry().top()
    assert downmix.geometry().bottom() <= decoder.geometry().top()
    assert decoder.geometry().bottom() <= buffering.geometry().top()
    assert decoder.geometry().right() <= host.width()
    for control in (check, downmix, decoder):
        assert control.isVisible()
        assert control.width() >= control.sizeHint().width(), control
