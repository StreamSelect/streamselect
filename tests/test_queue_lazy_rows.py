"""The Watch Queue builds row widgets only as rows come into view.

An 841-entry queue held 4,187 widgets and 58 MB to show the ten rows that fit
(measured 2026-11-16). These tests drive a real, shown section: what is on
screen is drawn, what is far below is not built yet, scrolling builds it, the
filter still searches everything, and rows keep their height either way.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from PyQt6 import sip
from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtWidgets import QApplication

from streamselect.core.repositories.queue import QueueEntry
from streamselect.gui.sidebar.lazy_rows import MARGIN_ROWS, ROLE_PENDING_ROW
from streamselect.gui.sidebar.queue import WatchQueueSection
from tests.conftest import destroy_widget

N = 200


def _entry(i: int) -> QueueEntry:
    return QueueEntry(queue_id=i, channel_id=f"c{i}", channel_name=f"Title {i:03d}",
                      media_type="movie", last_played=None, channel=None,
                      search_title=f"Title {i:03d}",
                      added_at=datetime(2026, 1, 1) + timedelta(minutes=i))


def _section(qapp):
    from streamselect.core.config import Config

    _section.before = _top_levels()
    sec = WatchQueueSection(Config(), db=None)
    sec.resize(260, 480)
    sec.show()
    sec._populate_rows([_entry(i) for i in range(N)])
    for _ in range(200):
        QApplication.processEvents()
        if sec._build_handle is None or sec._build_handle.done:
            break
    for _ in range(5):
        QApplication.processEvents()
    return sec


def _top_levels() -> set[int]:
    """The C++ addresses of the top-level widgets now. Not ``id()`` of the
    Python wrappers: topLevelWidgets() hands back temporaries, Python reuses a
    freed id, and the section's stray button could match a stale one and be
    left alive — a teardown leak seen only in full runs (2026-11-17)."""
    return {sip.unwrapinstance(w) for w in QApplication.topLevelWidgets()}


def _destroy(sec) -> None:
    """The section and any top-level it made (a header button that is not parented)."""
    strays = [w for w in QApplication.topLevelWidgets()
              if sip.unwrapinstance(w) not in _section.before and w is not sec]
    destroy_widget(sec, *strays)


def _rows(sec):
    lst = sec._list
    return [lst.item(i) for i in range(lst.count())
            if isinstance(lst.item(i).data(Qt.ItemDataRole.UserRole), dict)]


def _in_view(sec, item) -> bool:
    """Is any of *item* on screen: inside the list's viewport AND the section's
    scroll area, measured in the section's own coordinates."""
    vp = sec._list.viewport()
    rect = sec._list.visualItemRect(item)
    if not rect.isValid() or item.isHidden():
        return False
    row = QRect(vp.mapTo(sec, rect.topLeft()), rect.size())
    outer = sec.content_scroll.viewport()
    seen = (QRect(outer.mapTo(sec, QPoint(0, 0)), outer.size())
            .intersected(QRect(vp.mapTo(sec, QPoint(0, 0)), vp.size())))
    return row.intersects(seen)


def test_rows_in_view_are_drawn_and_rows_far_below_are_not_built(qapp):
    sec = _section(qapp)
    try:
        rows = _rows(sec)
        assert len(rows) == N, "every entry has its item, built or not"
        visible = [r for r in rows if _in_view(sec, r)]
        assert visible, "the section shows some rows"
        for item in visible:
            widget = sec._list.itemWidget(item)
            assert widget is not None, "a row on screen is never blank"
            assert widget.isVisible() and widget.height() >= sec._list.visualItemRect(item).height() - 1
        built = sum(sec._list.itemWidget(r) is not None for r in rows)
        assert built <= len(visible) + 2 * MARGIN_ROWS + 4, f"{built} of {N} built"
        assert sec._list.itemWidget(rows[-1]) is None, "the last row waits until it is near"
    finally:
        _destroy(sec)


def test_scrolling_builds_the_rows_that_come_into_view(qapp):
    sec = _section(qapp)
    try:
        outer = sec.content_scroll.verticalScrollBar()
        for _ in range(5):                             # until the layout has settled:
            sec._list.scrollToBottom()                 # the list's own bar...
            outer.setValue(outer.maximum())            # ...and the section's
            QApplication.processEvents()
        rows = _rows(sec)
        bottom = [r for r in rows if _in_view(sec, r)]
        assert bottom and rows[-1] in bottom
        assert all(sec._list.itemWidget(r) is not None for r in bottom)
    finally:
        _destroy(sec)


def test_unbuilt_rows_already_have_their_final_height(qapp):
    """The scrollbar is right from the start: a row does not change height when built."""
    sec = _section(qapp)
    try:
        rows = _rows(sec)
        waiting = [r for r in rows if r.data(ROLE_PENDING_ROW) is not None]
        built = [r for r in rows if sec._list.itemWidget(r) is not None]
        assert waiting and built
        height = built[0].sizeHint().height()
        assert height > 0 and all(r.sizeHint().height() == height for r in waiting)
        before = waiting[-1].sizeHint()
        sec._build_pending(waiting[-1])
        assert sec._list.itemWidget(waiting[-1]).sizeHint().height() == before.height()
    finally:
        _destroy(sec)


def test_in_the_sidebar_only_what_the_section_shows_is_built(qapp):
    """The real layout: ``fit_to_rows`` makes the list as tall as all its rows
    inside the section's one scroll area (15,225 px for 845 rows, measured), so
    the LIST's own rect says every row is visible. Only the rows the section's
    scroll area shows may be built, and scrolling THAT bar builds more."""
    sec = _section(qapp)
    try:
        rows = _rows(sec)
        sec.fit_to_rows(sec._list)
        for _ in range(5):
            QApplication.processEvents()
        assert sec._list.viewport().height() > sec.content_scroll.viewport().height() * 4

        shown = [r for r in rows if _in_view(sec, r)]
        assert shown and all(sec._list.itemWidget(r) is not None for r in shown)
        built = sum(sec._list.itemWidget(r) is not None for r in rows)
        assert built <= len(shown) + 2 * MARGIN_ROWS + 4, f"{built} of {N} built"

        bar = sec.content_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        QApplication.processEvents()
        shown = [r for r in rows if _in_view(sec, r)]
        assert rows[-1] in shown and all(sec._list.itemWidget(r) is not None for r in shown)
    finally:
        _destroy(sec)


def test_the_filter_finds_a_row_that_was_never_built_and_draws_it(qapp):
    sec = _section(qapp)
    try:
        last = _rows(sec)[-1]
        assert sec._list.itemWidget(last) is None
        sec._set_filter_visible(True, save=False)
        sec._filter.setText("title 000")              # the oldest: last in Never Watched
        QApplication.processEvents()
        shown = [r for r in _rows(sec) if not r.isHidden()]
        assert shown == [last]
        assert sec._list.itemWidget(last) is not None and _in_view(sec, last)
    finally:
        _destroy(sec)


def test_a_section_filled_while_hidden_draws_its_rows_when_shown(qapp):
    """Collapsed at launch, a short queue fills, then the user opens it: the list
    fits, so no scroll range changes — the Show alone has to build the rows."""
    from streamselect.core.config import Config

    _section.before = _top_levels()
    sec = WatchQueueSection(Config(), db=None)
    sec.resize(260, 480)
    sec._populate_rows([_entry(i) for i in range(6)])
    for _ in range(5):
        QApplication.processEvents()
    try:
        rows = _rows(sec)
        assert sum(sec._list.itemWidget(r) is not None for r in rows) < len(rows), \
            "hidden: rows wait"
        sec.show()
        for _ in range(5):
            QApplication.processEvents()
        shown = [r for r in rows if _in_view(sec, r)]
        assert len(shown) == len(rows), "six rows fit"
        assert all(sec._list.itemWidget(r) is not None for r in shown)
    finally:
        _destroy(sec)
