"""Finding what's playing in the sidebar's Watch Queue, for the playback menu.

Reads the rows the section has already built, so the number is the place you can
see: the sidebar orders by Continue Watching, then newest first, not by the stored
position. Its own module because the section's file is at its size floor.
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt


def _queue_rows(section: Any) -> list:
    """The section's real queue rows in display order, without Alerts-Matched rows."""
    rows = [item for group in section._groups for item, _hay in group.rows]
    return [item for item in rows
            if (item.data(Qt.ItemDataRole.UserRole) or {}).get("grain") in ("channel", "episode")]


def queue_place(section: Any, content_id: str | None) -> tuple[int | None, int]:
    """``(1-based place or None, rows in the queue)`` for one channel or episode id."""
    rows = _queue_rows(section)
    for place, item in enumerate(rows, start=1):
        if content_id and section._row_matches(item, content_id):
            return place, len(rows)
    return None, len(rows)


def reveal_queue_row(section: Any, content_id: str) -> bool:
    """Open the section and select the row. False if the row has since left the queue."""
    item = next((i for i in _queue_rows(section) if section._row_matches(i, content_id)), None)
    if item is None:
        return False
    if section._filter.text():
        section._filter.clear()  # a filter could be hiding the very row
    section.set_collapsed(False)
    section._list.setCurrentItem(item)
    section._list.scrollToItem(item)
    return True
