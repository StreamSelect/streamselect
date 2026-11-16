"""Build a sidebar list's row widgets only as they come into view.

A row is a ``QListWidgetItem`` (data, tooltip, height: cheap) plus a chip-row
WIDGET on it (a dozen Qt widgets: not cheap). The Watch Queue built a widget for
every entry up front, so an 841-entry queue held 4,187 widgets, more than half
the app's, and 58 MB, to show the ten rows that fit (measured 2026-11-16).

Every item is still created up front, so filtering, counts, selection and the
row readers that branch on ``UserRole`` work exactly as before. Only the widget
waits: an item carries its builder under :data:`ROLE_PENDING_ROW` until it comes
within :data:`MARGIN_ROWS` of the viewport, and is then built in place.

Heights cannot wait — the scrollbar needs every row's height up front, and a
row whose height changed when built would make the list jump. So the first row
of each *shape* is built at once and measured, and later rows of that shape take
its size. The caller names the shape: anything that changes the row's height
(its kind, the density, whether a second line is drawn) belongs in it.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QPoint, QSize, Qt, QTimer

#: Where an item keeps the callable that builds its widget, until it is built.
ROLE_PENDING_ROW = Qt.ItemDataRole.UserRole + 40
#: Rows built beyond the visible ones, above and below, so scrolling rarely
#: meets an unbuilt row.
MARGIN_ROWS = 20


def _row_size(row) -> QSize:
    """Width 0: the item spans the viewport; the row's own height governs."""
    return QSize(0, row.sizeHint().height())


class _ViewWatcher(QObject):
    """Schedules a pass when the list's viewport is shown or resized.

    The scrollbars cannot see everything: a section collapsed while its rows
    were added, then expanded with a list that fits, changes no scroll range,
    and its rows would stay blank. Qt sends a Show to the viewport when a hidden
    parent becomes visible.
    """

    def __init__(self, schedule, parent):
        super().__init__(parent)
        self._schedule = schedule

    def eventFilter(self, obj, event):  # noqa: N802 — Qt override
        if event.type() in (QEvent.Type.Show, QEvent.Type.Resize):
            self._schedule()
        return False


class LazyRowMixin:
    """For a section that adds chip rows to ``self._list``."""

    def _install_lazy_rows(self, list_widget) -> None:
        """Build pending rows whenever what is in view can have changed:
        either scrollbar moving or changing range, or the list being shown or
        resized (:class:`_ViewWatcher`)."""
        # A sidebar list does not scroll itself: it grows to its rows inside the
        # section's one scroll area (``content_scroll``), so THAT scrollbar is
        # what moves the view. Both are watched, so a standalone list works too.
        bars = [list_widget.verticalScrollBar()]
        outer = self.__dict__.get("content_scroll")
        if outer is not None:
            bars.append(outer.verticalScrollBar())
        for bar in bars:
            bar.valueChanged.connect(self._materialize_visible)
            bar.rangeChanged.connect(self._schedule_materialize)
        viewport = list_widget.viewport()
        self._lazy_view_watcher = _ViewWatcher(self._schedule_materialize, viewport)
        viewport.installEventFilter(self._lazy_view_watcher)

    def _add_lazy_row(self, item, shape: tuple, make_row, size_of=_row_size) -> None:
        """Add *item* to the list; build its widget now or when it comes into view.

        Args:
            item: The row's item, data and tooltip already set.
            shape: Everything that decides the row's height, e.g.
                ``("entry", density, has_second_line)``.
            make_row: Builds the row widget; called at most once.
            size_of: The item's size hint from a built row.
        """
        self._list.addItem(item)
        sizes = self.__dict__.setdefault("_lazy_row_sizes", {})
        size = sizes.get(shape)
        if size is None:                    # first of its shape: build it, and measure
            row = make_row()
            sizes[shape] = size_of(row)
            item.setSizeHint(sizes[shape])
            self._list.setItemWidget(item, row)
            return
        item.setSizeHint(size)
        item.setData(ROLE_PENDING_ROW, make_row)
        self._schedule_materialize()

    def _schedule_materialize(self, *_args) -> None:
        """Coalesce many adds (a chunked build) into one pass after them."""
        if not self.__dict__.get("_materialize_queued"):
            self._materialize_queued = True
            QTimer.singleShot(0, self._materialize_visible)

    def _materialize_visible(self, *_args) -> None:
        """Build the widgets of the rows in view, and :data:`MARGIN_ROWS` around them."""
        self._materialize_queued = False
        lst = self.__dict__.get("_list")
        if lst is None or lst.count() == 0:
            return
        # What is really on screen: the viewport clipped by every parent — in the
        # sidebar, the section's scroll area, where the list is as tall as all
        # its rows (15,225 px for 845 rows, measured) and its own rect says
        # "everything is visible".
        seen = lst.viewport().visibleRegion().boundingRect()
        if seen.isEmpty():
            return                       # collapsed or not shown: nothing to draw
        first = lst.indexAt(QPoint(0, seen.top())).row()
        if first < 0:
            # Not laid out yet: building "everything" here would undo the point.
            # The layout's scroll-range change schedules a pass.
            return
        last = lst.indexAt(QPoint(0, seen.bottom())).row()
        last = lst.count() - 1 if last < 0 else last      # the rows end inside the view
        # Walk back from the top for the margin above, then forward through the
        # view and the margin below — counting only rows the filter shows.
        above, index = 0, first - 1
        while index >= 0 and above < MARGIN_ROWS:
            above += self._build_pending(lst.item(index))
            index -= 1
        shown, index = 0, first
        while index < lst.count() and (index <= last or shown < MARGIN_ROWS):
            built = self._build_pending(lst.item(index))
            if index > last:
                shown += built
            index += 1

    def _build_pending(self, item) -> int:
        """Build *item*'s widget if it is waiting for one; 1 if it is a shown row."""
        if item is None or item.isHidden():
            return 0
        make_row = item.data(ROLE_PENDING_ROW)
        if make_row is not None:
            item.setData(ROLE_PENDING_ROW, None)
            self._list.setItemWidget(item, make_row())
        return 1
