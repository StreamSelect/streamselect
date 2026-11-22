"""Sports: how old the listings are, and a Refresh (owner, 2026-11-20).

The owner left the app open overnight and saw no new games: the network had been
down, then the source posted the next day's games after the 3-hourly live refresh
had run, and nothing on screen said how old the listings were, so the view looked
stuck. A discreet line under the sort row now says when the listings were last
refreshed, with a Refresh beside it that runs the live-only refresh of the active
sources (the same lane the timer uses, not Refresh All).
"""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from streamselect.core.time_display import clock_text
from streamselect.gui import theme as _theme


def listings_text(when: datetime | None, *, failed: bool = False, refreshing: bool = False,
                  now: datetime | None = None) -> str:
    """The line's words. *when* is the oldest active source's last live refresh,
    in local time; a failed refresh says so rather than leave an old time looking current."""
    if refreshing:
        return "Refreshing listings…"
    if when is None:
        stamp = ""
    else:
        now = now or datetime.now()
        stamp = clock_text(when) if when.date() == now.date() else f"{when:%a} {clock_text(when)}"
    if failed:
        return f"Refresh failed · listings from {stamp}" if stamp else "Refresh failed"
    return f"Listings from {stamp}" if stamp else "Listings not refreshed yet"


def build_freshness_row(text: str, on_refresh) -> tuple[QWidget, QLabel, QPushButton]:
    """The right-aligned line: the time, then a small Refresh."""
    box = QWidget()
    h = QHBoxLayout(box)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    h.addStretch(1)
    label = QLabel(text)
    _theme.style(label, "TEXT_SM_MUTED")
    label.setToolTip("When the games' channel listings were last fetched from your sources")
    h.addWidget(label)
    button = QPushButton("Refresh")
    button.setFlat(True)
    _theme.style(button, "LINK_BTN_SM")
    button.setToolTip("Fetch the live channel listings from your sources now, then look for games")
    button.clicked.connect(on_refresh)
    h.addWidget(button)
    return box, label, button
