"""Splitter handles: left-click collapses THEIR panel, right-click maximizes it.

User report: clicking the handle between the sidebar and the centre grew
the sidebar over the centre, while the details handle collapsed details as
expected. Handle ``i`` sits before panel ``i``, so the sidebar's handle (1) was
acting on the centre (panel 1). The accident is kept on purpose, as right-click.

Sizes are read from the painted widget geometry, not ``sizes()``, because that
is what the user sees.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QContextMenuEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QWidget

from streamselect.gui.collapsible_splitter import CollapsibleSplitter
from streamselect.gui.main_window import MainWindow
from tests.conftest import destroy_widget

SIDEBAR, CENTRE, DETAILS = 0, 1, 2
SIDEBAR_HANDLE, DETAILS_HANDLE = 1, 2


@pytest.fixture
def window(qapp):
    """The main splitter's real shape: minimums, stretch and the details cap."""
    splitter = CollapsibleSplitter(Qt.Orientation.Horizontal)
    for minimum in (200, 400, 300):
        panel = QWidget()
        panel.setMinimumWidth(minimum)
        splitter.addWidget(panel)
    splitter.widget(DETAILS).setMaximumWidth(500)
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)
    splitter.setStretchFactor(2, 0)
    splitter.resize(1600, 600)
    splitter.setSizes([340, 860, 400])
    splitter.show()
    qapp.processEvents()
    yield splitter
    destroy_widget(splitter)


def _widths(splitter) -> list[int]:
    QApplication.processEvents()
    return [
        splitter.widget(i).geometry().width() if splitter.sizes()[i] else 0
        for i in range(splitter.count())
    ]


def _left_click(splitter, handle_index: int) -> None:
    QTest.mouseClick(splitter.handle(handle_index), Qt.MouseButton.LeftButton)


def _right_click(splitter, handle_index: int) -> None:
    handle = splitter.handle(handle_index)
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(1, 1), handle.mapToGlobal(QPoint(1, 1)))
    QApplication.sendEvent(handle, event)


def test_left_click_on_the_sidebar_handle_collapses_the_sidebar(window):
    centre_before = _widths(window)[CENTRE]
    details_before = _widths(window)[DETAILS]
    _left_click(window, SIDEBAR_HANDLE)
    widths = _widths(window)
    assert widths[SIDEBAR] == 0
    assert widths[CENTRE] > centre_before, "the centre takes the room, it does not vanish"
    assert widths[DETAILS] == details_before


def test_left_click_on_the_details_handle_still_collapses_details(window):
    sidebar_before = _widths(window)[SIDEBAR]
    _left_click(window, DETAILS_HANDLE)
    widths = _widths(window)
    assert widths[DETAILS] == 0
    assert widths[SIDEBAR] == sidebar_before
    assert widths[CENTRE] > 0


def test_left_click_again_restores_exactly(window):
    before = _widths(window)
    for handle in (SIDEBAR_HANDLE, DETAILS_HANDLE):
        _left_click(window, handle)
        assert _widths(window) != before
        _left_click(window, handle)
        assert _widths(window) == before


def test_left_click_opens_a_panel_the_other_flank_left_collapsed(window):
    """Both collapsed: each handle reopens its own panel, not its neighbour's."""
    _left_click(window, SIDEBAR_HANDLE)
    _left_click(window, DETAILS_HANDLE)
    _left_click(window, SIDEBAR_HANDLE)
    widths = _widths(window)
    assert widths[SIDEBAR] > 0 and widths[DETAILS] == 0


def test_two_panel_splitter_acts_on_the_fixed_panel(qapp):
    """The filter column's splitter: [fixed column | stretching list]."""
    splitter = CollapsibleSplitter(Qt.Orientation.Horizontal)
    try:
        splitter.addWidget(QWidget())
        splitter.addWidget(QWidget())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.resize(900, 400)
        splitter.setSizes([200, 700])
        splitter.show()
        qapp.processEvents()
        _left_click(splitter, 1)
        assert splitter.sizes()[0] == 0 and splitter.sizes()[1] > 0
    finally:
        destroy_widget(splitter)


def test_right_click_grows_the_sidebar_over_the_centre_and_keeps_details(window):
    before = _widths(window)
    _right_click(window, SIDEBAR_HANDLE)
    widths = _widths(window)
    assert widths[CENTRE] == 0
    assert widths[SIDEBAR] > before[SIDEBAR] + before[CENTRE] - 10
    assert widths[DETAILS] == before[DETAILS]


def test_right_click_again_restores_exactly(window):
    before = _widths(window)
    _right_click(window, SIDEBAR_HANDLE)
    _right_click(window, SIDEBAR_HANDLE)
    assert _widths(window) == before


def test_details_maximize_stops_at_its_ceiling_and_the_centre_keeps_the_rest(window):
    before = _widths(window)
    _right_click(window, DETAILS_HANDLE)
    widths = _widths(window)
    assert widths[DETAILS] == 500
    assert widths[SIDEBAR] == before[SIDEBAR]
    assert widths[CENTRE] > 0, "the cap must not leave a hole or give the sidebar the slack"
    _right_click(window, DETAILS_HANDLE)
    assert _widths(window) == before


def test_right_click_on_the_other_handle_switches_the_maximize(window):
    before = _widths(window)
    _right_click(window, SIDEBAR_HANDLE)
    _right_click(window, DETAILS_HANDLE)
    widths = _widths(window)
    assert widths[SIDEBAR] == before[SIDEBAR], "the sidebar went back before details grew"
    assert widths[DETAILS] == 500


def test_left_click_on_a_maximized_panel_collapses_it_and_the_centre_returns(window):
    centre_before = _widths(window)[CENTRE]
    _right_click(window, SIDEBAR_HANDLE)
    _left_click(window, SIDEBAR_HANDLE)
    widths = _widths(window)
    assert widths[SIDEBAR] == 0
    assert widths[CENTRE] > centre_before
    _left_click(window, SIDEBAR_HANDLE)
    assert _widths(window)[SIDEBAR] == 340, "collapse remembered the pre-maximize width"


def test_maximizing_a_collapsed_panel_restores_to_collapsed_with_its_width_kept(window):
    _left_click(window, SIDEBAR_HANDLE)
    _right_click(window, SIDEBAR_HANDLE)
    assert _widths(window)[CENTRE] == 0
    _right_click(window, SIDEBAR_HANDLE)
    assert _widths(window)[SIDEBAR] == 0
    _left_click(window, SIDEBAR_HANDLE)
    assert _widths(window)[SIDEBAR] == 340


def test_a_drag_ends_the_maximize(window):
    _right_click(window, SIDEBAR_HANDLE)
    window.moveSplitter(600, SIDEBAR_HANDLE)
    dragged = window.sizes()
    assert window.settled_sizes() == dragged, "after a drag the sizes on screen ARE the layout"
    _right_click(window, SIDEBAR_HANDLE)
    assert _widths(window)[CENTRE] == 0, "the next right-click maximizes, it restores nothing stale"


def test_explore_leaving_undoes_a_maximize_made_inside_it(window):
    """Explore shuts both flanks and reopens them through expand_panel."""
    before = _widths(window)
    window.collapse_panel(SIDEBAR)
    window.collapse_panel(DETAILS)
    _right_click(window, SIDEBAR_HANDLE)
    window.expand_panel(SIDEBAR)
    window.expand_panel(DETAILS)
    assert _widths(window) == before


def _save_host(splitter, **config) -> SimpleNamespace:
    return SimpleNamespace(
        view_mode="list",
        config=SimpleNamespace(save=MagicMock(), **config),
        main_splitter=splitter,
    )


def test_a_maximize_is_never_saved_as_the_layout(window):
    host = _save_host(window, sidebar_width=1, details_pane_width=1,
                      sidebar_pane_visible=False, details_pane_visible=False)
    _right_click(window, SIDEBAR_HANDLE)
    MainWindow.save_splitter_sizes(host, _persist=False)
    assert host.config.sidebar_width == 340
    assert host.config.sidebar_pane_visible is True


def test_collapsing_keeps_the_width_and_records_the_state(window):
    host = _save_host(window, sidebar_width=340, details_pane_width=400,
                      sidebar_pane_visible=True, details_pane_visible=True)
    _left_click(window, SIDEBAR_HANDLE)
    _left_click(window, DETAILS_HANDLE)
    MainWindow.save_splitter_sizes(host, _persist=False)
    assert host.config.sidebar_width == 340 and host.config.details_pane_width == 400
    assert host.config.sidebar_pane_visible is False
    assert host.config.details_pane_visible is False


def test_a_handle_gesture_announces_itself_for_saving(window):
    calls = []
    window.panels_toggled.connect(lambda: calls.append(1))
    _left_click(window, SIDEBAR_HANDLE)
    _right_click(window, DETAILS_HANDLE)
    assert len(calls) == 2


def test_the_handle_is_wide_enough_to_grab(window):
    """User report: used often, so doubled from 7px (12px on macOS)."""
    assert window.handle(SIDEBAR_HANDLE).geometry().width() >= 14
