"""The guided tour rings the real controls and says where it lives (onboarding 6).

Offered once after a new source's first load, and always from Tools ▸ Take the
tour. Explore is a just-in-time tip, not a stop (tests/test_just_in_time_tips.py).
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtWidgets import QLineEdit, QPushButton, QWidget


class _Host(QWidget):
    """A window carrying the controls the stops look for, at known places."""

    def __init__(self, config_dir):
        from streamselect.core.config import Config
        from streamselect.core.notifications import NotificationManager
        super().__init__()
        self.resize(1200, 800)
        self.config = Config(config_dir=str(config_dir))
        self.notification_manager = NotificationManager()
        self.search_input = QLineEdit(self)
        self.search_input.setGeometry(120, 30, 250, 30)
        self.channels_list = QWidget(self)
        self.channels_list.setGeometry(220, 80, 600, 700)
        self._nav_track = QWidget(self)
        self._nav_track.setGeometry(400, 30, 400, 30)
        self._filter_chip = QPushButton("Exclusions", self)
        self._filter_chip.setGeometry(1050, 30, 110, 30)
        self.sidebar_splitter = QWidget(self)
        self.sidebar_splitter.setGeometry(0, 80, 200, 300)
        # Stretched far past its content, like the real Sources line.
        self.sources_strip = QWidget(self)
        self.sources_strip.setGeometry(0, 390, 200, 400)
        self._sources_lbl = QLineEdit("Sources", self.sources_strip)
        self._sources_lbl.setGeometry(10, 185, 120, 30)
        self.sidebar_sections = {}
        self.picked_themes = []

    def _set_theme_from_menu(self, name):
        self.picked_themes.append(name)
        self.config.theme_name = name


@pytest.fixture
def host(qapp, owned_widgets, tmp_path):
    h = owned_widgets.own(_Host(tmp_path))
    h.show()
    qapp.processEvents()
    return h


def _start(host):
    from streamselect.gui.guided_tour import start_tour
    tour = start_tour(host)
    return tour


@pytest.mark.parametrize("stop", [1, 2, 3, 4, 5])  # 0 is centred, 6 (Sources) tight: below
def test_each_stop_rings_its_real_control(host, stop):
    from streamselect.gui.guided_tour import TOUR_STOPS

    tour = _start(host)
    for _ in range(stop):
        tour.next()
    target = TOUR_STOPS[stop].target(host)
    target_rect = QRect(target.mapTo(host, QPoint(0, 0)), target.size())
    assert tour.hole() is not None and tour.hole().contains(target_rect), (
        f"stop {stop} rings {tour.hole()}, the control is at {target_rect}")
    card = tour._card.geometry()
    assert not card.intersects(tour.hole()), "the card covers the control it explains"
    assert tour.rect().contains(card), "the card runs off the window"
    tour.end()


def test_sources_is_ringed_around_what_it_draws_not_its_stretched_box(host):
    tour = _start(host)
    for _ in range(6):
        tour.next()
    assert tour._title.text() == "Sources"
    label = host._sources_lbl
    drawn = QRect(label.mapTo(host, QPoint(0, 0)), label.size())
    ring = tour.hole()
    assert ring.contains(drawn), "the ring misses the Sources line itself"
    assert ring.height() < host.sources_strip.height() / 3, (
        f"the ring circles the stretched box ({ring.height()} px of mostly nothing)")
    tour.end()


def test_a_missing_control_centres_the_card_tall_enough_for_its_text(host, qapp):
    host.sources_strip.hide()
    tour = _start(host)
    for _ in range(6):
        tour.next()
    qapp.processEvents()
    assert tour.hole() is None
    body = tour._body
    assert body.height() >= body.heightForWidth(body.width()), "the explanation is cut off"
    tour.end()


def test_taking_the_tour_records_it(host):
    from streamselect.gui.just_in_time_tips import TOUR_KEY, seen

    assert not seen(host, TOUR_KEY)
    _start(host).end()
    assert seen(host, TOUR_KEY), "taken once, it must not be offered again"


def test_keys_step_and_escape_ends_with_where_to_find_it(host, qapp):
    from PyQt6.QtTest import QTest

    from streamselect.gui.guided_tour import TOUR_MENU_PATH

    tour = _start(host)
    QTest.keyClick(tour, Qt.Key.Key_Right)
    assert tour.current() == 1
    QTest.keyClick(tour, Qt.Key.Key_Left)
    assert tour.current() == 0
    assert not tour._back_btn.isEnabled()
    QTest.keyClick(tour, Qt.Key.Key_Escape)
    assert "_tour" not in host.__dict__
    (note,) = host.notification_manager.get_visible_notifications()
    assert TOUR_MENU_PATH in note.message, "the end must say where the tour lives"


def test_the_last_stop_finishes_on_done(host):
    tour = _start(host)
    for _ in range(6):
        tour.next()
    assert tour._next_btn.text() == "Done"
    tour._next_btn.click()
    assert "_tour" not in host.__dict__


def test_the_tools_menu_handler_starts_the_tour(host):
    """Tools ▸ Take the tour runs the real menu handler over the window."""
    from streamselect.gui.main_window_menu_actions import _MenuActionsMixin

    _MenuActionsMixin.start_tour(host)
    tour = host.__dict__.get("_tour")
    assert tour is not None and tour.isVisible() and tour.current() == 0
    tour.end()


def _legend_stop(tour):
    from streamselect.gui.guided_tour import TOUR_STOPS
    index = next(i for i, s in enumerate(TOUR_STOPS) if s.legend)
    for _ in range(index):
        tour.next()
    return TOUR_STOPS[index]


def _mark_colour(label):
    from PyQt6.QtGui import QColor
    image = label.pixmap().toImage()
    inked = [QColor(image.pixel(x, y)) for x in range(image.width())
             for y in range(image.height()) if QColor.fromRgba(image.pixel(x, y)).alpha() > 200]
    assert inked, f"{label.objectName()} draws nothing"
    return inked[len(inked) // 2].name()


def test_the_row_kinds_stop_shows_each_mark_as_the_list_paints_it(host, qapp):
    """A tester could not tell which rows join a live broadcast and which
    start from the beginning; the stop shows the three marks, live in the
    accent like the rows (channel_list_delegate._paint_kind_icon)."""
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QLabel

    from streamselect.gui import theme

    tour = _start(host)
    stop = _legend_stop(tour)
    qapp.processEvents()
    assert [r for r, _ in stop.legend] == ["live", "movie", "series"]
    marks = {r: tour._card.findChild(QLabel, f"tourLegend_{r}") for r in ("live", "movie", "series")}
    assert all(m is not None and m.isVisible() for m in marks.values())
    def near(a, b):     # antialiasing rounds a channel by a step
        a, b = QColor(a), QColor(b)
        return max(abs(a.red() - b.red()), abs(a.green() - b.green()),
                   abs(a.blue() - b.blue())) <= 4
    assert near(_mark_colour(marks["live"]), theme.COLOR_ACCENT), "live is not the accent"
    assert near(_mark_colour(marks["movie"]), theme.COLOR_TEXT)
    assert not near(theme.COLOR_ACCENT, theme.COLOR_TEXT)
    card = tour._card.rect()
    for mark in marks.values():
        row = mark.parentWidget()
        bottom = row.mapTo(tour._card, row.rect().bottomLeft()).y()
        assert bottom <= card.bottom(), "the legend runs off the card"
    assert tour.hole() is not None and not tour._card.geometry().intersects(tour.hole())
    tour.next()
    assert not tour._legend.isVisible(), "the legend stays on the stop it belongs to"
    tour.end()


def test_the_tour_opens_on_every_theme_and_a_click_switches_to_it(host, qapp):
    """A new user is shown the themes first; a click applies and saves through
    the Style menu's handler, with no Apply step."""
    from PyQt6.QtWidgets import QPushButton

    from streamselect.gui import theme

    host.config.theme_name = "Midnight"
    tour = _start(host)
    qapp.processEvents()
    rows = {n: tour._card.findChild(QPushButton, f"tourTheme_{n}")
            for n in theme.available_themes()}
    assert all(r is not None and r.isVisible() for r in rows.values())
    assert [n for n, r in rows.items() if r.isChecked()] == ["Midnight"]
    rows["Daylight"].click()
    assert host.picked_themes == ["Daylight"]
    assert [n for n, r in rows.items() if r.isChecked()] == ["Daylight"]
    card, inner = tour._card.geometry(), tour.rect()
    assert abs(card.center().x() - inner.center().x()) <= 2, "the theme card is not centred"
    last = rows[theme.available_themes()[-1]]
    assert last.mapTo(tour._card, last.rect().bottomLeft()).y() <= tour._card.rect().bottom(), (
        "the theme list runs off the card")
    tour.next()
    assert not tour._themes.isVisible(), "the theme list stays on its own card"
    tour.end()


def test_each_swatch_is_painted_in_its_own_theme(qapp):
    from PyQt6.QtGui import QColor

    from streamselect.gui import theme_palettes
    from streamselect.gui.tour_theme_picker import swatch

    def corner(name):     # inside the border, on the theme's background
        return QColor(swatch(name).toImage().pixel(2, 13)).lightness()

    assert corner("Daylight") > 200 and corner("Midnight") < 60
    accent = QColor(swatch("Gruvbox").toImage().pixel(35, 12)).name()
    assert accent == QColor(theme_palettes.PALETTES["Gruvbox"]["COLOR_ACCENT"]).name()


def test_the_theme_card_rings_style_in_the_menu_bar(qapp, owned_widgets, tmp_path):
    from PyQt6.QtWidgets import QMainWindow

    from streamselect.core.config import Config
    from streamselect.core.notifications import NotificationManager
    from streamselect.gui.guided_tour import start_tour

    win = owned_widgets.own(QMainWindow())
    win.resize(1200, 800)
    win.config = Config(config_dir=str(tmp_path))
    win.notification_manager = NotificationManager()
    for title in ("&File", "&View", "&Style", "&Layout"):
        win.menuBar().addMenu(title)
    win.show()
    qapp.processEvents()
    tour = start_tour(win)
    bar = win.menuBar()
    style = next(a for a in bar.actions() if a.text() == "&Style")
    entry = bar.actionGeometry(style)
    entry = QRect(bar.mapTo(win, entry.topLeft()), entry.size())
    assert tour.hole() is not None and tour.hole().contains(entry)
    assert tour.hole().width() < entry.width() * 3, "the ring circles the whole menu bar"
    assert not tour._card.geometry().intersects(tour.hole())
    tour.end()
