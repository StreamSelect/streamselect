"""Just-in-time tips: once per profile, at the moment the control is useful.

User report: Explore was a tour stop with nothing to point at on a new
install; it is a tip shown the first time a list has something in it, ringing
that list's count (the count is what opens Explore).
"""
from __future__ import annotations

import time

import pytest
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtWidgets import QPushButton, QWidget


class _Section(QWidget):
    """A sidebar list: a count button, and how many rows it has."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setGeometry(0, 100, 200, 30)
        self._status_label = QPushButton("0", self)
        self._status_label.setGeometry(170, 5, 24, 20)
        self.count = 0

    def item_count(self):
        return self.count


class _Host(QWidget):
    def __init__(self, config_dir):
        from streamselect.core.config import Config
        from streamselect.core.notifications import NotificationManager
        super().__init__()
        self.resize(1000, 700)
        self.config = Config(config_dir=str(config_dir))
        self.notification_manager = NotificationManager()
        self.section = _Section(self)
        self._playback_health_label = QPushButton("18s buffer · 6.2 Mbps · 0 drops", self)
        self._playback_health_label.setGeometry(600, 10, 220, 24)


@pytest.fixture
def host(qapp, owned_widgets, tmp_path):
    h = owned_widgets.own(_Host(tmp_path))
    h.show()
    qapp.processEvents()
    return h


def _wait(qapp, cond, secs=3.0):
    end = time.time() + secs
    while not cond() and time.time() < end:
        qapp.processEvents()
        time.sleep(0.02)
    return cond()


def test_an_empty_list_shows_no_tip(host, qapp):
    from streamselect.gui.just_in_time_tips import offer_explore_tip

    offer_explore_tip(host, host.section)
    assert not _wait(qapp, lambda: host.__dict__.get("_tour") is not None, 1.0)


def test_the_first_list_with_titles_gets_the_explore_tip_on_its_count(host, qapp):
    from streamselect.gui.just_in_time_tips import offer_explore_tip

    host.section.count = 3
    offer_explore_tip(host, host.section)
    assert _wait(qapp, lambda: host.__dict__.get("_tour") is not None)
    tip = host._tour
    assert tip._title.text() == "Explore" and tip._next_btn.text() == "Got it"
    assert tip._back_btn.isHidden() and tip._end_btn.isHidden(), "a tip is one card"
    count = host.section._status_label
    assert tip.hole().contains(QRect(count.mapTo(host, QPoint(0, 0)), count.size())), (
        "the tip must ring the count, which is the way into Explore")
    tip._next_btn.click()
    assert "_tour" not in host.__dict__


def test_a_tip_shows_once_per_profile(host, qapp):
    from streamselect.gui.just_in_time_tips import offer_explore_tip

    host.section.count = 2
    offer_explore_tip(host, host.section)
    assert _wait(qapp, lambda: host.__dict__.get("_tour") is not None)
    host._tour.end()
    assert "explore" in host.config.tips_seen
    offer_explore_tip(host, host.section)
    assert not _wait(qapp, lambda: host.__dict__.get("_tour") is not None, 1.0)


def test_a_tip_waits_while_the_tour_is_on_screen(host, qapp):
    from streamselect.gui.guided_tour import start_tour
    from streamselect.gui.just_in_time_tips import offer_explore_tip

    tour = start_tour(host)
    host.section.count = 1
    offer_explore_tip(host, host.section)
    _wait(qapp, lambda: False, 1.0)
    assert host.__dict__.get("_tour") is tour, "a tip must never replace the tour"
    assert "explore" not in host.config.tips_seen, "an unshown tip is not 'seen'"
    tour.end()


def test_tips_seen_is_a_profile_preference():
    """Stored in the database profile, never config.yaml (user report)."""
    from streamselect.core.config import Config, PROFILE

    extra = Config.model_fields["tips_seen"].json_schema_extra
    assert extra == PROFILE


@pytest.mark.parametrize(("taken", "offered"), [(False, True), (True, False)])
def test_the_ready_notice_offers_the_tour_until_it_is_taken(qapp, tmp_path, taken, offered):
    from unittest.mock import MagicMock

    from streamselect.core.config import Config
    from streamselect.core.notifications import NotificationManager
    from streamselect.gui.main_window_source_add import _SourceAddMixin

    host = MagicMock()
    host.config = Config(config_dir=str(tmp_path))
    host.config.tips_seen = ["tour"] if taken else []
    host.notification_manager = NotificationManager()
    host.__dict__["_filter_chip"] = None
    _SourceAddMixin._show_first_scan_notice(host, 4, 2)
    (note,) = host.notification_manager.get_visible_notifications()
    labels = [a[0] for a in note.actions]
    assert ("Take the tour" in labels) is offered
    assert "Open Exclusions" in labels


def test_the_first_play_explains_the_playback_line(host, qapp):
    """Tester report: the playback line's menu (audio, Normalize volume,
    Downmix) went unnoticed; the first play rings that line once."""
    from streamselect.gui.just_in_time_tips import offer_playback_tip

    offer_playback_tip(host)
    assert _wait(qapp, lambda: host.__dict__.get("_tour") is not None)
    tip = host._tour
    assert "Normalize volume" in tip._body.text() and "mono" in tip._body.text()
    line = host._playback_health_label
    assert tip.hole().contains(QRect(line.mapTo(host, QPoint(0, 0)), line.size()))
    tip._next_btn.click()
    offer_playback_tip(host)
    assert not _wait(qapp, lambda: host.__dict__.get("_tour") is not None, 1.0)


def test_a_hidden_playback_line_waits_for_a_later_play(host, qapp):
    from streamselect.gui.just_in_time_tips import offer_playback_tip

    host._playback_health_label.hide()
    offer_playback_tip(host)
    assert not _wait(qapp, lambda: host.__dict__.get("_tour") is not None, 1.0)
    assert "playback" not in (host.config.tips_seen or [])


def test_a_play_that_advances_offers_the_playback_tip(qapp):
    """The seam: playback_start_watch's first-progress branch calls it."""
    from unittest.mock import patch

    import streamselect.gui.playback_start_watch as watch
    from tests.test_play_count_needs_progress import _host

    host = _host()
    watch.arm(host, watch.PlayAttempt("ch-1", "T1", "http://x"))
    with patch("streamselect.gui.just_in_time_tips.offer_playback_tip") as offer:
        watch.on_loaded_tick(host, 0.0, False, cache_duration=3.0)
        offer.assert_not_called()
        watch.on_loaded_tick(host, 1.0, False, cache_duration=3.0)
    offer.assert_called_once_with(host)
