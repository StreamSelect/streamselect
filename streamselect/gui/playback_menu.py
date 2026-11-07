"""The menu behind the header's live playback readout.

The settings that change a stream while it plays, at the moment you notice you
need them, plus the tracks and queue of the window the readout is showing. Rebuilt
on every click, so it can never disagree with Settings → Playback or the player.
The setting labels and options are that tab's own.
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import QMenu

from streamselect.core.players.live_playback import LivePlayback, LiveTrack
from streamselect.gui import deferred_config_save as _cfgsave
from streamselect.gui.settings_player_rows import (
    DECODER_OPTIONS, DECODER_TIP, DOWNMIX_OPTIONS, DOWNMIX_TIP, NORMALIZE_LABEL, NORMALIZE_TIP,
)

_OVERRIDE_TIP = "Off while Override all is on in Settings → Playback"


def _change(host: Any, field: str, value: object, message: str) -> None:
    """Store one setting and bring every open player window in line with it."""
    setattr(host.config, field, value)
    _cfgsave.save_soon(host)
    host._apply_player_settings()
    host.status(message, ms=4000)


def _text(value: str) -> str:
    """Menu text for a title: a bare & would underline the next letter and vanish."""
    return value.replace("&", "&&")


def _add_line(menu: QMenu, text: str) -> None:
    """Add a line that only informs, which is why it is not clickable."""
    menu.addAction(_text(text)).setEnabled(False)


def _add_play_queue(host: Any, menu: QMenu, live: LivePlayback) -> None:
    """Add the play queue: a list to jump around in, and the next item one click away.

    Names are StreamSelect's own titles or a plain "Item 3", never what mpv holds for them.
    """
    if not (live.count > 1 and live.position):
        _add_line(menu, "Play queue: nothing after this")
        return
    def name(index: int) -> str:
        return (live.queue_titles[index] if live.queue_titles else None) or f"Item {index + 1}"

    now = f"Play queue: {live.position} of {live.count}"
    sub = menu.addMenu(_text(f"{now} · {live.current_title}" if live.current_title else now))
    sub.setToolTipsVisible(True)
    group = QActionGroup(sub)
    group.setExclusive(True)
    for index in range(live.count):
        action = QAction(_text(f"{index + 1}. {name(index)}"), sub, checkable=True)
        playing = index == live.position - 1
        action.setChecked(playing)
        action.setEnabled(not playing)
        action.setToolTip("Jump to this item")
        action.triggered.connect(lambda _c, i=index: host._jump_play_queue(live.key, i, name(i)))
        group.addAction(action)
        sub.addAction(action)
    if live.position == live.count:
        _add_line(menu, "Last in the play queue")
    else:
        following = menu.addAction(_text(f"Next: {name(live.position)}"))
        following.setToolTip("Jump to this item")
        following.triggered.connect(
            lambda _c: host._jump_play_queue(live.key, live.position, name(live.position)))


def _add_watch_queue(host: Any, menu: QMenu, live: LivePlayback) -> None:
    """Add where this sits in the Watch Queue. Its place opens that row in the sidebar."""
    if live.watch_queue_total is None:
        return
    if live.watch_queue_place and live.content:
        line = menu.addAction(f"Watch Queue: {live.watch_queue_place} of {live.watch_queue_total}")
        line.setToolTip("Show it in the Watch Queue")
        line.triggered.connect(lambda _c: host._reveal_in_watch_queue(live.content[1]))
    elif live.watch_queue_total:
        _add_line(menu, "Not in Watch Queue")
    else:
        _add_line(menu, "Watch Queue is empty")


def _add_setting_menu(host: Any, menu: QMenu, title: str, field: str, options, tip: str,
                      enabled: bool) -> None:
    """Add a submenu of exclusive choices for one setting, naming the current one."""
    current = getattr(host.config, field, options[0][0])
    current_label = next((label for value, label in options if value == current), options[0][1])
    sub = menu.addMenu(f"{title}: {current_label}")
    sub.setToolTipsVisible(True)
    sub.menuAction().setEnabled(enabled)
    sub.menuAction().setToolTip(tip if enabled else _OVERRIDE_TIP)
    group = QActionGroup(sub)
    group.setExclusive(True)
    for value, label in options:
        action = QAction(label, sub, checkable=True)
        action.setChecked(value == current)
        action.setToolTip(tip)
        action.triggered.connect(
            lambda _c, v=value, name=label: _change(host, field, v, f"{title}: {name}"))
        group.addAction(action)
        sub.addAction(action)


def _add_track_menu(host: Any, menu: QMenu, live: LivePlayback, title: str, prop: str,
                    tracks: tuple[LiveTrack, ...], allow_off: bool) -> None:
    """Add one submenu of tracks; long lists are why these aren't flat like the settings."""
    if not tracks:
        menu.addAction(f"{title}: none in this stream").setEnabled(False)
        return
    current = next((t.label for t in tracks if t.selected), "Off")
    sub = menu.addMenu(_text(f"{title}: {current}"))
    sub.setToolTipsVisible(True)
    group = QActionGroup(sub)
    group.setExclusive(True)
    choices = [(t.track_id, t.label, t.selected) for t in tracks]
    if allow_off:
        choices.append(("no", "Off", not any(t.selected for t in tracks)))
    for value, label, selected in choices:
        action = QAction(_text(label), sub, checkable=True)
        action.setChecked(selected)
        action.setToolTip("Changes this player window only")
        action.triggered.connect(lambda _c, v=value, name=label: host._send_player_command(
            ["set_property", prop, v], live.key, f"{title}: {name}"))
        group.addAction(action)
        sub.addAction(action)


def _add_live_section(host: Any, menu: QMenu, live: LivePlayback) -> None:
    """Add the shown window's queue and tracks."""
    if not live.readable:
        _add_line(menu, "This player isn't answering, so tracks and queue aren't shown")
    else:
        if live.content:
            details = menu.addAction("Show details")
            details.setToolTip("Show what's playing in the details pane")
            details.triggered.connect(lambda _c: host._show_playing_details(live.content))
        _add_play_queue(host, menu, live)
        _add_watch_queue(host, menu, live)
        menu.addSeparator()
        _add_track_menu(host, menu, live, "Audio track", "aid", live.audio, allow_off=False)
        _add_track_menu(host, menu, live, "Subtitles", "sid", live.subs, allow_off=True)
    menu.addSeparator()


def build_playback_menu(host: Any, live: LivePlayback | None = None) -> QMenu:
    """Build the playback menu from the current config and the shown window's state.

    Args:
        host: The MainWindow.
        live: The window the readout is showing; None when nothing is playing.

    Returns:
        A new menu, parented to *host*.
    """
    config = host.config
    enabled = not getattr(config, "mpv_args_override_all", False)
    menu = QMenu(host)
    menu.setToolTipsVisible(True)
    if live is not None:
        _add_live_section(host, menu, live)

    normalize = QAction(NORMALIZE_LABEL, menu, checkable=True)
    normalize.setChecked(bool(getattr(config, "normalize_volume", False)))
    normalize.setEnabled(enabled)
    normalize.setToolTip(NORMALIZE_TIP if enabled else _OVERRIDE_TIP)
    normalize.triggered.connect(lambda checked: _change(
        host, "normalize_volume", checked, f"{NORMALIZE_LABEL}: {'on' if checked else 'off'}"))
    menu.addAction(normalize)

    _add_setting_menu(host, menu, "Downmix audio", "audio_downmix", DOWNMIX_OPTIONS, DOWNMIX_TIP,
                      enabled)
    _add_setting_menu(host, menu, "Video decoder", "video_decoder", DECODER_OPTIONS, DECODER_TIP,
                      enabled)
    menu.addSeparator()

    # This click used to cycle windows; it has to stay reachable.
    if len(host.player_manager.active_keys()) > 1:
        next_player = menu.addAction("Next player window")
        next_player.setToolTip("Show the next open player in this readout")
        next_player.triggered.connect(lambda _c: host._on_health_readout_clicked())

    settings = menu.addAction("Playback settings…")
    settings.setToolTip("Open Settings → Playback")
    settings.triggered.connect(lambda _c: host.open_settings("Playback"))
    return menu
