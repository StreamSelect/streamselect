"""The menu behind the header's live playback readout."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QWidget

from streamselect.core.players.live_playback import LivePlayback, live_playback_from_props
from streamselect.gui import deferred_config_save, playback_menu
from streamselect.core.database import EpisodeDB
from streamselect.core.repositories import RepositoryFactory
from streamselect.gui.app_header import _ClickableNavLabel
from streamselect.gui.playback_watch_queue import queue_place, reveal_queue_row
from tests.conftest import wire_episode_watch_signal


@pytest.fixture
def host(monkeypatch, qtbot):
    monkeypatch.setattr(deferred_config_save, "save_soon", MagicMock())
    widget = QWidget()
    qtbot.addWidget(widget)
    widget.config = SimpleNamespace(normalize_volume=False, audio_downmix="auto",
                                    video_decoder="auto", mpv_args_override_all=False)
    widget.player_manager = MagicMock()
    widget.player_manager.active_keys.return_value = ["a"]
    widget._apply_player_settings = MagicMock()
    widget.status = MagicMock()
    widget._on_health_readout_clicked = MagicMock()
    widget.open_settings = MagicMock()
    widget._send_player_command = MagicMock()
    widget._jump_play_queue = MagicMock()
    widget._reveal_in_watch_queue = MagicMock()
    widget._show_playing_details = MagicMock()
    return widget


def _all_actions(menu):
    """Every entry, submenus included."""
    found = []
    for action in menu.actions():
        found.append(action)
        if action.menu():
            found += _all_actions(action.menu())
    return found


def _action(menu, text):
    return next(a for a in _all_actions(menu) if a.text() == text)


def _texts(menu):
    return [a.text() for a in menu.actions() if a.text()]


def test_normalize_stores_saves_and_reaches_open_players(host):
    menu = playback_menu.build_playback_menu(host)
    _action(menu, "Normalize volume").trigger()
    assert host.config.normalize_volume is True
    deferred_config_save.save_soon.assert_called_once_with(host)
    host._apply_player_settings.assert_called_once_with()
    assert "on" in host.status.call_args.args[0]


@pytest.mark.parametrize("label,field,value", [("To mono", "audio_downmix", "mono"),
                                               ("Software", "video_decoder", "software")])
def test_a_choice_stores_and_reaches_open_players(host, label, field, value):
    _action(playback_menu.build_playback_menu(host), label).trigger()
    assert getattr(host.config, field) == value
    host._apply_player_settings.assert_called_once_with()


def test_the_menu_marks_what_is_currently_set(host):
    host.config.normalize_volume = True
    host.config.audio_downmix = "stereo"
    host.config.video_decoder = "software"
    menu = playback_menu.build_playback_menu(host)
    checked = {a.text() for a in _all_actions(menu) if a.isChecked()}
    assert checked == {"Normalize volume", "To stereo", "Software"}
    assert "Downmix audio: To stereo" in _texts(menu)
    assert "Video decoder: Software" in _texts(menu)


def test_override_all_greys_the_settings_and_says_why(host):
    host.config.mpv_args_override_all = True
    menu = playback_menu.build_playback_menu(host)
    for label in ("Normalize volume", "Downmix audio: Off", "Video decoder: Automatic"):
        action = _action(menu, label)
        assert not action.isEnabled()
        assert "Override all" in action.toolTip()
    assert _action(menu, "Playback settings…").isEnabled()


def test_next_player_only_when_there_is_another_and_it_still_cycles(host):
    assert "Next player window" not in _texts(playback_menu.build_playback_menu(host))
    host.player_manager.active_keys.return_value = ["a", "b"]
    _action(playback_menu.build_playback_menu(host), "Next player window").trigger()
    host._on_health_readout_clicked.assert_called_once_with()


def test_settings_entry_opens_the_playback_tab(host):
    _action(playback_menu.build_playback_menu(host), "Playback settings…").trigger()
    host.open_settings.assert_called_once_with("Playback")


def test_menu_renders_every_entry_in_order_with_room_for_its_text(host):
    menu = playback_menu.build_playback_menu(host)
    menu.ensurePolished()
    tops = [menu.actionGeometry(a).top() for a in menu.actions()]
    assert tops == sorted(tops) and len(set(tops)) == len(tops)
    longest = max(menu.fontMetrics().horizontalAdvance(t) for t in _texts(menu))
    assert menu.sizeHint().width() >= longest
    assert menu.actionGeometry(_action(menu, "Downmix audio: Off")).height() > 0


def test_clicking_the_readout_emits_clicked(qtbot):
    label = _ClickableNavLabel("3600s buffer")
    qtbot.addWidget(label)
    seen = []
    label.clicked.connect(lambda: seen.append(True))
    from PyQt6.QtCore import QPoint, QPointF, Qt
    from PyQt6.QtGui import QMouseEvent
    label.mousePressEvent(QMouseEvent(
        QMouseEvent.Type.MouseButtonPress, QPointF(QPoint(2, 2)), QPointF(QPoint(2, 2)),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    assert seen == [True]


# ── the shown window's tracks and queue ──────────────────────────────────────

URL = "http://203.0.113.5/user/secret/1.mkv"
TRACKS = [
    {"id": 1, "type": "video", "codec": "h264"},
    {"id": 1, "type": "audio", "lang": "eng", "codec": "aac", "demux-channel-count": 6,
     "selected": True, "main-selection": 0},
    {"id": 2, "type": "audio", "lang": "spa", "title": "Commentary", "codec": "ac3"},
    {"id": 1, "type": "sub", "lang": "fre", "codec": "subrip"},
    {"id": 2, "type": "sub", "codec": "ass", "hearing-impaired": True},
]


def _live(tracks=TRACKS, pos=1, count=3, titles=("Pilot", "Tom & Jerry", "Finale"), place=(2, 5),
          content=("episode", "e2")):
    props = {"track-list": tracks, "playlist-pos": pos, "playlist-count": count}
    return replace(live_playback_from_props("k", props, list(titles)), content=content,
                   watch_queue_place=place[0], watch_queue_total=place[1])


def _sub(menu, prefix):
    return next(a.menu() for a in menu.actions() if a.text().startswith(prefix))


def _lines(menu):
    return [a.text().replace("&&", "&") for a in menu.actions()
            if a.text() and not a.isEnabled()]


def test_audio_lists_the_tracks_marks_the_current_one_and_switches_it(host):
    menu = playback_menu.build_playback_menu(host, _live())
    audio = _sub(menu, "Audio track: English")
    assert [a.text() for a in audio.actions()] == [
        "English · AAC · 5.1", "Spanish · Commentary · AC3"]
    assert [a.isChecked() for a in audio.actions()] == [True, False]
    audio.actions()[1].trigger()
    host._send_player_command.assert_called_once_with(
        ["set_property", "aid", 2], "k", "Audio track: Spanish · Commentary · AC3")


def test_subtitles_can_be_switched_on_and_off(host):
    menu = playback_menu.build_playback_menu(host, _live())
    subs = _sub(menu, "Subtitles: Off")
    assert [a.text() for a in subs.actions()] == [
        "French · SUBRIP", "Track 2 · CC · ASS", "Off"]
    assert subs.actions()[2].isChecked()
    subs.actions()[0].trigger()
    host._send_player_command.assert_called_with(["set_property", "sid", 1], "k",
                                                 "Subtitles: French · SUBRIP")
    subs.actions()[2].trigger()
    host._send_player_command.assert_called_with(["set_property", "sid", "no"], "k",
                                                 "Subtitles: Off")


def test_a_stream_without_tracks_says_so(host):
    lines = _lines(playback_menu.build_playback_menu(host, _live(tracks=[])))
    assert "Audio track: none in this stream" in lines
    assert "Subtitles: none in this stream" in lines


def test_queue_shows_position_and_proper_titles(host):
    menu = playback_menu.build_playback_menu(host, _live())
    queue = _sub(menu, "Play queue: 2 of 3 · Tom && Jerry")
    assert [a.text() for a in queue.actions()] == ["1. Pilot", "2. Tom && Jerry", "3. Finale"]
    assert "Next: Finale" in _texts(menu)
    assert "Watch Queue: 2 of 5" in _texts(menu)


def test_a_queue_item_jumps_when_clicked_and_the_current_one_is_inert(host):
    menu = playback_menu.build_playback_menu(host, _live())
    queue = _sub(menu, "Play queue")
    assert queue.actions()[1].isChecked() and not queue.actions()[1].isEnabled()
    queue.actions()[0].trigger()
    host._jump_play_queue.assert_called_once_with("k", 0, "Pilot")


def test_next_jumps_to_the_following_item(host):
    _action(playback_menu.build_playback_menu(host, _live()), "Next: Finale").trigger()
    host._jump_play_queue.assert_called_once_with("k", 2, "Finale")


def test_the_watch_queue_place_opens_that_row(host):
    _action(playback_menu.build_playback_menu(host, _live()), "Watch Queue: 2 of 5").trigger()
    host._reveal_in_watch_queue.assert_called_once_with("e2")


def test_show_details_loads_what_is_playing(host):
    _action(playback_menu.build_playback_menu(host, _live()), "Show details").trigger()
    host._show_playing_details.assert_called_once_with(("episode", "e2"))


def test_show_details_is_absent_when_what_is_playing_is_unknown(host):
    menu = playback_menu.build_playback_menu(host, _live(content=None))
    assert "Show details" not in _texts(menu)


def test_a_title_keeps_its_ampersand_rather_than_making_a_shortcut(host):
    menu = playback_menu.build_playback_menu(host, _live())
    assert any("Tom && Jerry" in a.text() for a in _all_actions(menu))


def test_a_url_is_never_shown_even_when_it_is_all_there_is(host):
    live = _live(titles=(URL, URL, URL))
    assert live.current_title is None and live.next_title is None
    menu = playback_menu.build_playback_menu(host, live)
    texts = [a.text() for a in _all_actions(menu)]
    assert not [t for t in texts if "://" in t or "secret" in t]
    assert {"Play queue: 2 of 3", "1. Item 1", "3. Item 3", "Next: Item 3"} <= set(texts)


def test_mpvs_playlist_and_media_title_are_never_asked_for():
    from streamselect.core.players.live_playback import LIVE_PROPS
    assert "playlist" not in LIVE_PROPS and "media-title" not in LIVE_PROPS


def test_titles_that_do_not_line_up_with_mpv_name_nothing(host):
    """An item that failed to queue would otherwise put the wrong name beside Next."""
    live = _live(titles=("Pilot", "Finale"))
    assert live.current_title is None and live.next_title is None
    assert live.position == 2 and live.count == 3


@pytest.mark.parametrize("live,expected", [
    ({"pos": 2}, "Last in the play queue"),
    ({"pos": 0, "count": 1, "titles": ("Pilot",)}, "Play queue: nothing after this"),
    ({"place": (None, 4)}, "Not in Watch Queue"),
    ({"place": (None, 0)}, "Watch Queue is empty"),
])
def test_queue_states_read_plainly(host, live, expected):
    assert expected in _lines(playback_menu.build_playback_menu(host, _live(**live)))


def test_a_player_that_did_not_answer_says_so_and_keeps_the_settings(host):
    menu = playback_menu.build_playback_menu(host, LivePlayback(key="k"))
    assert any("isn't answering" in line for line in _lines(menu))
    assert "Normalize volume" in _texts(menu)
    assert not any(t.startswith("Audio track") for t in _texts(menu))


def test_tracks_stay_available_under_override_all(host):
    """Override all drops StreamSelect's launch flags. Picking a track isn't one."""
    host.config.mpv_args_override_all = True
    audio = _sub(playback_menu.build_playback_menu(host, _live()), "Audio track")
    assert all(a.isEnabled() for a in audio.actions())


def test_the_live_section_renders_above_the_settings(host):
    menu = playback_menu.build_playback_menu(host, _live())
    menu.ensurePolished()
    top = {a.text(): menu.actionGeometry(a).top() for a in menu.actions() if a.text()}
    assert top["Next: Finale"] < top["Audio track: English · AAC · 5.1"]
    assert top["Audio track: English · AAC · 5.1"] < top["Normalize volume"]


def test_no_watch_queue_line_when_the_section_is_not_in_the_sidebar(host):
    menu = playback_menu.build_playback_menu(host, _live(place=(None, None)))
    assert not [t for t in _texts(menu) if "Watch Queue" in t]


def test_the_submenus_render_with_room_for_their_choices(host):
    menu = playback_menu.build_playback_menu(host, _live())
    menu.ensurePolished()
    downmix = _sub(menu, "Downmix audio")
    downmix.ensurePolished()
    assert [a.text() for a in downmix.actions()] == ["Off", "To stereo", "To mono"]
    assert downmix.sizeHint().width() >= downmix.fontMetrics().horizontalAdvance("To stereo")
    assert menu.actionGeometry(_action(menu, "Normalize volume")).top() < (
        menu.actionGeometry(downmix.menuAction()).top())


# ── jumping keeps watch history honest ───────────────────────────────────────

def _jump_host(db):
    from streamselect.gui.main_window_menu_actions import _MenuActionsMixin
    from streamselect.gui.main_window_streaming import _StreamingMixin

    class Host(_MenuActionsMixin, _StreamingMixin):
        pass

    jump = Host.__new__(Host)
    wire_episode_watch_signal(jump)
    jump.db = db
    jump.executor = SimpleNamespace(submit=lambda fn, *a, **k: fn(*a, **k))
    jump.config = SimpleNamespace(watch_complete_threshold=0.9, prompt_after_autoplay=True)
    jump.player_manager = MagicMock()
    jump._send_player_command = MagicMock()
    jump._watch_tracking = {"k": {
        "media_type": "episode", "played_via": "manual", "last_seen_pos": 0,
        "queue": [{"content_id": "e1"}, {"content_id": "e2"}, {"content_id": "e3"}],
    }}
    return jump


def _seed_episodes(db):
    with db.session_scope() as session:
        for num in (1, 2, 3):
            session.add(EpisodeDB(id=f"e{num}", season_id="s1", series_id="ser1", provider_id="p1",
                                  episode_id=str(num), episode_num=num, season_num=1,
                                  title=f"Episode {num}"))
    with db.session_scope() as session:
        RepositoryFactory(session).episodes.record_watch_progress("e1", 300, 1500, 0.9, "manual")


def _tick(host, pos):
    host.player_manager.get_properties.return_value = {
        "time-pos": 5.0, "duration": 1500.0, "playlist-pos": pos}
    host._bg_capture_watch("k", dict(host._watch_tracking["k"]))


def _completed(db, episode_id):
    with db.session_scope(commit=False) as session:
        return bool(RepositoryFactory(session).episodes.get_by_id(episode_id).watch_completed)


def test_jumping_past_a_half_watched_episode_does_not_mark_it_watched(db):
    _seed_episodes(db)
    host = _jump_host(db)
    snapshot_before_the_jump = dict(host._watch_tracking["k"])
    host._jump_play_queue("k", 2, "Episode 3")
    host._send_player_command.assert_called_once_with(
        ["set_property", "playlist-pos", 2], "k", "Playing Episode 3")
    # A tick that took its snapshot just before the jump must not read it as played.
    host.player_manager.get_properties.return_value = {
        "time-pos": 5.0, "duration": 1500.0, "playlist-pos": 2}
    host._bg_capture_watch("k", snapshot_before_the_jump)
    assert _completed(db, "e1") is False


def test_playing_through_after_jumping_back_still_completes(db):
    """Jump back to the start: mpv running on from there is a real play-through."""
    _seed_episodes(db)
    host = _jump_host(db)
    host._watch_tracking["k"]["last_seen_pos"] = 2
    host._jump_play_queue("k", 0, "Episode 1")
    _tick(host, 0)
    _tick(host, 1)
    assert _completed(db, "e1") is True


def test_what_is_playing_follows_the_queue_not_the_item_that_started_it(db):
    host = _jump_host(db)
    host._playing_episodes = {"k": "e1"}
    assert host._playing_content("k", 3) == ("episode", "e3")
    assert host._playing_content("k", 9) is None
    del host._watch_tracking["k"]
    assert host._playing_content("k", 0) == ("episode", "e1")
    host._playing_episodes = {}
    host._playing_channels = {"k": "c1"}
    assert host._playing_content("k", 0) == ("channel", "c1")


def test_a_mixed_queue_uses_each_items_own_type(db):
    host = _jump_host(db)
    host._watch_tracking["k"]["queue"][1] = {"content_id": "m1", "media_type": "movie"}
    assert host._playing_content("k", 2) == ("channel", "m1")


# ── the sidebar's own order ──────────────────────────────────────────────────

def _section(qtbot, rows):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QListWidget, QListWidgetItem

    from streamselect.gui.sidebar.queue import WatchQueueSection

    section = SimpleNamespace(_filter=MagicMock(), set_collapsed=MagicMock(), _list=QListWidget(),
                              _row_matches=lambda item, key: WatchQueueSection._row_matches(
                                  None, item, key))
    qtbot.addWidget(section._list)
    section._filter.text.return_value = "needle"
    items = []
    for payload in rows:
        item = QListWidgetItem("row")
        item.setData(Qt.ItemDataRole.UserRole, payload)
        section._list.addItem(item)
        items.append((item, "row"))
    section._groups = [SimpleNamespace(rows=items)]
    return section


def test_the_place_counts_rows_as_shown_and_skips_alert_rows(qtbot):
    section = _section(qtbot, [{"grain": "matched_channel", "channel_id": "a"},
                               {"grain": "channel", "channel_id": "newest"},
                               {"grain": "episode", "episode_id": "e1", "channel_id": "s"},
                               {"grain": "channel", "channel_id": "oldest"}])
    assert queue_place(section, "e1") == (2, 3)
    assert queue_place(section, "oldest") == (3, 3)
    assert queue_place(section, "a") == (None, 3)
    assert queue_place(section, None) == (None, 3)


def test_revealing_opens_the_section_clears_the_filter_and_selects_the_row(qtbot):
    section = _section(qtbot, [{"grain": "channel", "channel_id": "x"},
                               {"grain": "channel", "channel_id": "y"}])
    assert reveal_queue_row(section, "y") is True
    section.set_collapsed.assert_called_once_with(False)
    section._filter.clear.assert_called_once_with()
    assert section._list.currentRow() == 1
    assert reveal_queue_row(section, "gone") is False
