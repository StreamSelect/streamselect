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


class _ActionBar:
    def __init__(self, row):
        self.like_button = QPushButton("+", row)
        self.not_interested_button = QPushButton("o", row)
        self.dislike_button = QPushButton("-", row)
        for i, b in enumerate((self.like_button, self.not_interested_button, self.dislike_button)):
            b.setGeometry(10 + 40 * i, 4, 36, 24)


class _Cast:
    def __init__(self, parent):
        self.chip = QPushButton("Nathan Fielder", parent)
        self.chip.setGeometry(10, 120, 120, 24)

    def person_chips(self, role):
        return [self.chip] if role == "cast" else []


class _Pane(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setGeometry(650, 100, 300, 400)
        row = QWidget(self)
        row.setGeometry(0, 40, 300, 32)
        self._action_bar = _ActionBar(row)
        self._cast = _Cast(self)


def test_the_first_title_explains_like_not_interested_and_dislike_then_cast(host, qapp):
    """Owner's guide: rating teaches Recommended; a cast name lists their work.
    The rating tip rings all three buttons; the cast tip waits for the next title."""
    from streamselect.gui.just_in_time_tips import offer_details_tips

    host.details_pane = _Pane(host)
    host.details_pane.show()
    qapp.processEvents()
    offer_details_tips(host)
    assert _wait(qapp, lambda: host.__dict__.get("_tour") is not None)
    tip = host._tour
    assert tip._title.text() == "Teach it your taste"
    bar = host.details_pane._action_bar
    for b in (bar.like_button, bar.not_interested_button, bar.dislike_button):
        assert tip.hole().contains(QRect(b.mapTo(host, QPoint(0, 0)), b.size())), b.text()
    tip._next_btn.click()
    offer_details_tips(host)
    assert _wait(qapp, lambda: host.__dict__.get("_tour") is not None)
    chip = host.details_pane._cast.chip
    assert host._tour._title.text() == "Cast and crew"
    assert host._tour.hole().contains(QRect(chip.mapTo(host, QPoint(0, 0)), chip.size()))


def test_a_cast_name_scrolled_out_of_view_waits_then_is_ringed_where_it_is(host, qapp):
    """Owner, 2026-11-12: the cast tip sat in the window's top-left corner while
    the names were at the bottom right of the details pane. The first name was
    below the pane's scrolled viewport; the ring was cut to nothing and the card
    fell back to the corner. Now the tip waits, and rings the name once on screen."""
    from PyQt6.QtWidgets import QScrollArea

    from streamselect.gui.just_in_time_tips import offer_details_tips

    pane = QScrollArea(host)
    pane.setGeometry(650, 300, 300, 300)
    inner = QWidget()
    inner.resize(280, 1200)
    pane.setWidget(inner)
    pane._cast = _Cast(inner)
    pane._cast.chip.setGeometry(10, 1000, 120, 24)     # far below the viewport
    host.config.tips_seen = ["rating"]
    host.details_pane = pane
    pane.show()
    qapp.processEvents()

    offer_details_tips(host)
    assert not _wait(qapp, lambda: host.__dict__.get("_tour") is not None, 1.0)
    assert "people" not in host.config.tips_seen, "an unshown tip is not 'seen'"

    pane.ensureWidgetVisible(pane._cast.chip)
    qapp.processEvents()
    offer_details_tips(host)
    assert _wait(qapp, lambda: host.__dict__.get("_tour") is not None)
    chip = pane._cast.chip
    chip_rect = QRect(chip.mapTo(host, QPoint(0, 0)), chip.size())
    assert host._tour.hole().contains(chip_rect)
    card = host._tour._card.geometry()
    # The card sits beside the name it explains: within one card height of it.
    assert abs(card.center().y() - chip_rect.center().y()) <= card.height() + chip_rect.height()
    assert card.right() >= pane.geometry().left(), "the card is not in the far corner"
    host._tour.end()


@pytest.mark.parametrize("view, chip, title", [
    ("discover", "discover_chip", "Discover"), ("recipe", "recipe_chip", "Recipe"),
    ("epg", "epg_chip", "EPG"), ("preferences", "prefs_chip", "Recommended"),
])
def test_each_view_explains_itself_once_on_its_chip(host, qapp, view, chip, title):
    from streamselect.gui.just_in_time_tips import offer_view_tip

    button = QPushButton(title, host)
    button.setGeometry(300, 10, 90, 26)
    button.show()
    setattr(host, chip, button)
    offer_view_tip(host, view)
    assert _wait(qapp, lambda: host.__dict__.get("_tour") is not None)
    assert host._tour._title.text() == title
    assert host._tour.hole().contains(QRect(button.mapTo(host, QPoint(0, 0)), button.size()))
    host._tour._next_btn.click()
    offer_view_tip(host, view)
    assert not _wait(qapp, lambda: host.__dict__.get("_tour") is not None, 1.0)


@pytest.mark.parametrize("view", ["epg", "preferences", "discover", "recipe"])
def test_switching_to_a_view_offers_its_tip(view):
    """The seam: each switch_to_*_view calls offer_view_tip with its view."""
    from unittest.mock import MagicMock, patch

    from streamselect.gui.main_window_menu_actions import _MenuActionsMixin
    from streamselect.gui.main_window_nav import _NavMixin

    host = MagicMock()
    host.__dict__.update(epg_status_label=MagicMock(), epg_refresh_btn=MagicMock())
    host.epg_view._provider_ids = []
    name = {"preferences": "switch_to_preferences_view", "epg": "switch_to_epg_view"}.get(
        view, f"switch_to_{view}_view")
    getattr(_NavMixin, name)(host)
    host._offer_view_tip.assert_called_once_with(view)
    with patch("streamselect.gui.just_in_time_tips.offer_view_tip") as offer:
        _MenuActionsMixin._offer_view_tip(host, view)
    offer.assert_called_once_with(host, view)


def test_show_tips_again_forgets_every_tip_but_the_tour(host):
    from streamselect.gui.just_in_time_tips import TOUR_KEY, reset_tips

    host.config.tips_seen = [TOUR_KEY, "explore", "playback", "view_epg"]
    assert reset_tips(host) == 3
    assert host.config.tips_seen == [TOUR_KEY]
