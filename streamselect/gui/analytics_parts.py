"""The parts analytics-style views are built from: cards, figure tiles, short bars, link labels.

Lifted out of the Sources editor's Analytics tab (``gui/source_analytics_tab.py``),
where they were private, so the Library breakdown view (Tools menu) is built
from the same parts rather than a copy (design "Library Breakdown", BV-Q3).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from streamselect.gui import cursor_affordance, icons
from streamselect.gui import theme as _theme
from streamselect.gui.chip_row import MiddleElideLabel
from streamselect.gui.progress_paint import ProgressBar

#: A short bar: long enough to compare, too short to be a page-wide empty track.
BAR_PX = 56


def text_label(text: str, role: str) -> QLabel:
    label = QLabel(text)
    _theme.style(label, role)
    return label


class AnalyticsCard(QFrame):
    """A card: a heading with a right-aligned subtitle over a body that loads on its own."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("analyticsCard")
        _theme.style(self, "ANALYTICS_CARD")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 12)
        outer.setSpacing(6)
        head = QHBoxLayout()
        self.title = QLabel(title)
        self.title.setWordWrap(True)
        _theme.style(self.title, "SECTION_TITLE_SM")
        head.addWidget(self.title, 1)
        self.subtitle = QLabel("")
        self.subtitle.setWordWrap(True)          # a long subtitle must not set a narrow editor's floor
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        _theme.style(self.subtitle, "META_HINT")
        head.addWidget(self.subtitle)
        outer.addLayout(head)
        self.body = QVBoxLayout()
        self.body.setSpacing(4)
        outer.addLayout(self.body)

    def text(self, html_text: str, role: str = "SECTION_HINT") -> QLabel:
        label = QLabel(html_text)
        label.setWordWrap(True)
        _theme.style(label, role)
        self.body.addWidget(label)
        return label

    def grid(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        self.body.addLayout(grid)
        return grid

    def show_all(self, hidden: list[QWidget], total: int) -> None:
        """Hide *hidden* behind a "Show all (N)" toggle that expands in place."""
        if not hidden:
            return
        for widget in hidden:
            widget.setVisible(False)
        more = f"{icons.show_all_icon} Show all ({total:,})"
        button = QPushButton(more)
        button.setToolTip(f"Show all {total:,} — {len(hidden):,} more rows")
        _theme.style(button, "LINK_BTN_SM")
        cursor_affordance.set_clickable(button)

        def toggle() -> None:
            opening = button.text() == more
            for widget in hidden:
                widget.setVisible(opening)
            button.setText("Show fewer" if opening else more)

        button.clicked.connect(toggle)
        row = QHBoxLayout()
        row.addWidget(button)
        row.addStretch(1)
        self.body.addLayout(row)


class FigureTile(QFrame):
    """One headline figure over its caption; hidden until its query answers."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("analyticsCard")
        _theme.style(self, "ANALYTICS_CARD")
        box = QVBoxLayout(self)
        box.setContentsMargins(14, 8, 16, 10)
        box.setSpacing(0)
        self.figure = text_label("", "STAT_FIGURE")
        box.addWidget(self.figure)
        self.caption = text_label("", "META_HINT")
        self.caption.setWordWrap(True)
        box.addWidget(self.caption)
        box.addStretch(1)
        self.hide()

    def set(self, figure: str, caption: str, *, warn: bool = False) -> None:
        self.figure.setText(figure)
        _theme.style(self.figure, "STAT_FIGURE_WARN" if warn else "STAT_FIGURE")
        self.caption.setText(caption)
        self.show()


#: Stat blocks per row on a card. Three keep each block wide enough for a
#: one-line caption at the editor's narrowest two-column width.
STATS_ACROSS = 3


def stat_grid(section: AnalyticsCard, stats) -> None:
    """(figure, caption, detail) blocks in an even grid: the number first, what it
    counts under it, and any breakdown below that — Playback and What you watch."""
    grid = QGridLayout()
    grid.setHorizontalSpacing(18)
    grid.setVerticalSpacing(12)
    for col in range(STATS_ACROSS):
        grid.setColumnStretch(col, 1)
    for i, (figure, caption, *detail) in enumerate(stats):
        block = QVBoxLayout()
        block.setSpacing(0)
        block.addWidget(text_label(figure, "STAT_FIGURE_MD"))
        for text in (caption, *(d for d in detail if d)):
            line = text_label(text, "META_HINT")
            line.setWordWrap(True)               # a long caption wraps rather than widen the card
            block.addWidget(line)
        block.addStretch(1)
        grid.addLayout(block, *divmod(i, STATS_ACROSS))
    section.body.addLayout(grid)


class LinkLabel(MiddleElideLabel):
    """A middle-eliding label that is clicked like a link (region names, Q18)."""

    clicked = pyqtSignal()

    def __init__(self, text: str, tooltip: str) -> None:
        super().__init__(text, color_token="COLOR_LINK")
        self.setToolTip(tooltip)
        cursor_affordance.set_clickable(self)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 — Qt override
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


def short_bar(fraction: float | None, width: int = BAR_PX) -> ProgressBar:
    return ProgressBar((fraction or 0.0) * 100.0, width=width, height=6, warn_at=None)
