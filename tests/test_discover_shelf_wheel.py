"""An up/down wheel turn over a Discover shelf scrolls the page, never the shelf.

Owner report: scrolling down Discover, the pointer lands on a shelf (or its
scrollbar) and the shelf slides sideways while the page stops. Qt's default for a
scroll area with nothing to scroll vertically hands the turn to its sideways bar.
A sideways swipe still moves the shelf, and Shift turns the wheel sideways.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QApplication, QScrollArea, QVBoxLayout, QWidget

from streamselect.core.config import Config
from streamselect.core.discovery_engine import ContentCard
from streamselect.gui.discover_shelf import _Shelf


@pytest.fixture()
def page(qapp, owned_widgets, tmp_path):
    outer = owned_widgets.own(QScrollArea())
    outer.setWidgetResizable(True)
    outer.resize(600, 400)
    inner = QWidget()
    v = QVBoxLayout(inner)
    cards = [ContentCard(channel_id=f"c{i}", title=f"T{i}", media_type="movie", thumbnail_url=None,
                         rating=7.0, year=2000, genre="x") for i in range(40)]
    shelves = [_Shelf(f"S{i}", f"genre:{i}", cards, MagicMock(), Config(config_dir=tmp_path)) for i in range(4)]
    for s in shelves:
        v.addWidget(s)
    outer.setWidget(inner)
    outer.show()
    for _ in range(30):
        QApplication.processEvents()
    return outer, shelves[0]


def _wheel(target, dx, dy, mods=Qt.KeyboardModifier.NoModifier):
    QApplication.sendEvent(target, QWheelEvent(
        QPointF(10, 10), QPointF(target.mapToGlobal(QPoint(10, 10))), QPoint(0, 0), QPoint(dx, dy),
        Qt.MouseButton.NoButton, mods, Qt.ScrollPhase.NoScrollPhase, False))


@pytest.mark.parametrize("where", ["row", "scrollbar"])
def test_an_up_down_turn_over_a_shelf_scrolls_the_page(page, where):
    outer, shelf = page
    target = shelf._scroll_area.viewport() if where == "row" else shelf._scroll_area.horizontalScrollBar()
    h0, v0 = shelf._scroll_area.horizontalScrollBar().value(), outer.verticalScrollBar().value()
    _wheel(target, 0, -120)
    assert shelf._scroll_area.horizontalScrollBar().value() == h0, "the shelf did not slide"
    assert outer.verticalScrollBar().value() > v0, "the page scrolled down"


def test_a_sideways_swipe_and_shift_wheel_still_move_the_shelf(page):
    _outer, shelf = page
    bar = shelf._scroll_area.horizontalScrollBar()
    _wheel(shelf._scroll_area.viewport(), -120, 0)
    after_swipe = bar.value()
    assert after_swipe > 0
    _wheel(shelf._scroll_area.viewport(), 0, -120, Qt.KeyboardModifier.ShiftModifier)
    assert bar.value() > after_swipe
