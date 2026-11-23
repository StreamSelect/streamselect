"""The bar under Resume, and the live timer for a playing episode (owner, 2026-11-23).

"On the resume button below the Resume ##:## line there should be a progress bar
that shows how far into the episode the user has watched." And the Resume time
lagged mpv: an episode's label only moved on each 20 s progress save, while a movie's
Play button runs a per-second timer. An episode now gets that timer while it is the
one playing, and Resume steps aside until it stops.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from streamselect.core.repositories.dtos import EpisodeDTO
from tests.test_series_episode_details import _fake_channel


def _bar(qapp, owned_widgets):
    from streamselect.core.config import Config
    from streamselect.gui.details_actions import _ActionBar
    bar = owned_widgets.own(_ActionBar(Config()))
    bar.resize(420, 80)
    bar.show()
    qapp.processEvents()
    return bar


def _fill_share(button, bar) -> float:
    """How much of the bar's track is painted in the fill colour, as rendered."""
    from streamselect.gui import theme
    from streamselect.gui.token_color import to_qcolor
    img = button.grab().toImage()
    fill = to_qcolor(theme.COLOR_ACCENT)
    g = bar.geometry()
    y = g.center().y()
    def near(c) -> bool:
        return abs(c.red() - fill.red()) + abs(c.green() - fill.green()) + abs(c.blue() - fill.blue()) < 40
    hits = sum(1 for x in range(g.left(), g.right() + 1) if near(img.pixelColor(x, y)))
    return hits / max(1, g.width())


class TestTheResumeBar:

    def test_the_bar_shows_how_far_in_along_the_bottom_of_resume(self, qapp, owned_widgets):
        ab = _bar(qapp, owned_widgets)
        ab.enter_episode_mode("S04E01")
        ab.set_resume(True, 987, 37)
        qapp.processEvents()
        bar, btn = ab._resume_bar, ab.resume_button
        assert bar.isVisibleTo(ab) and bar.pct == 37
        g = bar.geometry()
        assert g.bottom() < btn.height() and g.top() > btn.height() // 2, "along the bottom, inside the button"
        assert 0.25 < _fill_share(btn, bar) < 0.5, "about 37% of the track is filled"
        assert "37% in" in btn.toolTip()

    def test_nearly_the_end_fills_nearly_all_of_it(self, qapp, owned_widgets):
        ab = _bar(qapp, owned_widgets)
        ab.set_resume(True, 2400, 92)
        qapp.processEvents()
        assert _fill_share(ab.resume_button, ab._resume_bar) > 0.8

    def test_no_resume_no_bar(self, qapp, owned_widgets):
        ab = _bar(qapp, owned_widgets)
        ab.set_resume(True, 987, 37)
        ab.set_resume(False)
        assert not ab._resume_bar.isVisibleTo(ab)


class TestTheEpisodeTimer:

    def test_a_playing_episode_ticks_and_resume_steps_aside(self, qapp, owned_widgets):
        ab = _bar(qapp, owned_widgets)
        ab.enter_episode_mode("S04E01")
        ab.set_resume(True, 987, 37)
        ab.set_playing_active(991)
        qapp.processEvents()
        assert ab.play_button.text().endswith("16:31"), ab.play_button.text()
        assert not ab.resume_button.isVisibleTo(ab), "you are watching it: no lagging Resume"
        ab.set_resume(True, 1000, 38)       # a progress save while playing
        assert not ab.resume_button.isVisibleTo(ab) and ab.play_button.text().endswith("16:31")
        ab.clear_playing()
        assert ab.play_button.text() == "Start over" and ab.resume_button.isVisibleTo(ab)

    def test_a_series_root_never_ticks(self, qapp, owned_widgets):
        ab = _bar(qapp, owned_widgets)
        ab.set_primary_mode("browse")
        ab.set_playing_active(50)
        assert ab.play_button.text() == "Browse"

    def test_the_pane_lights_the_timer_for_the_episode_shown(self, qapp, owned_widgets):
        from streamselect.core.config import Config
        from streamselect.gui.details_pane import DetailsPaneWidget
        cache = MagicMock()
        cache.get_image_sync.return_value = None
        pane = owned_widgets.own(DetailsPaneWidget(Config(), cache, db=None))
        ep = EpisodeDTO(id=str(uuid.uuid4()), episode_num=1, season_num=4, title="Criminal Nature",
                        series_name="The Show", stream_url="http://example.com/e", duration="44:00",
                        is_watched=False, rating=None, watch_progress=987, watch_percent=37)
        pane.show_episode(ep, _fake_channel("series"))
        bar = pane._action_bar
        assert bar.resume_button.text() == "Resume 16:27" and bar._resume_bar.pct == 37
        pane.set_playing(ep.id, 991)
        assert bar._is_playing and bar.play_button.text().endswith("16:31")
        pane.set_playing("another-episode", 10)
        assert not bar._is_playing and bar.play_button.text() == "Start over"


def test_a_window_reports_the_episode_it_is_playing_now():
    """A queue's current entry (as of the last save), else the one started."""
    from streamselect.gui.main_window_menu_actions import _MenuActionsMixin
    from streamselect.gui.main_window_series_playback import _SeriesPlaybackMixin
    host = SimpleNamespace()
    host._playing_content = lambda k, p: _MenuActionsMixin._playing_content(host, k, p)
    queue = [{"content_id": "e1", "media_type": "episode"}, {"content_id": "e2", "media_type": "episode"}]
    host._watch_tracking = {"k": {"queue": queue, "last_seen_pos": 1}}
    host._playing_episodes = {"k": "e1"}
    assert _SeriesPlaybackMixin._playing_episode_id(host, "k") == "e2"
    host._watch_tracking = {}
    assert _SeriesPlaybackMixin._playing_episode_id(host, "k") == "e1"
    host._playing_episodes = {}
    assert _SeriesPlaybackMixin._playing_episode_id(host, "k") is None


def test_the_playback_poll_tells_the_pane_which_episode_is_playing(qapp):
    """An episode is no channel, so the poll found nothing to report and the pane
    never lit its timer for one. It now reports the episode the window plays."""
    from streamselect.gui.main_window_menu_actions import _MenuActionsMixin
    from streamselect.gui.main_window_series_playback import _SeriesPlaybackMixin
    from streamselect.gui.main_window_streaming import _StreamingMixin

    host = _StreamingMixin.__new__(_StreamingMixin)
    host.details_pane = MagicMock()
    host._playback_health_label = MagicMock()
    host._playing_channels = {}
    host._playing_episodes = {"k1": "ep1"}
    host._playing_content = lambda k, p: _MenuActionsMixin._playing_content(host, k, p)
    host._playing_episode_id = lambda k: _SeriesPlaybackMixin._playing_episode_id(host, k)
    host.player_manager = MagicMock()
    host.player_manager.active_keys.return_value = ["k1"]
    host._source_icon_for_key = lambda k: ""
    props = {"path": "http://stream", "demuxer-cache-duration": 5, "cache-speed": 1_000,
             "frame-drop-count": 0, "time-pos": 991}
    host._on_playback_health_ready(("k1", props))
    host.details_pane.set_playing.assert_called_once_with("ep1", 991)
