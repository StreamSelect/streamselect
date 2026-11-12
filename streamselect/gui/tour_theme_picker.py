"""The tour's first card: every theme in a list, applied the moment it is clicked.

A new user meets the default theme and is never told there are others (user
report). The list is the whole decision: a click switches and saves through
the Style menu's own handler, so there is no Apply step, and the tour's Next
and End tour buttons carry on or close as on every other card. Each row's
swatch is painted in THAT theme's colours, so the list shows what each one
looks like before it is chosen.
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QButtonGroup, QPushButton, QVBoxLayout, QWidget

from streamselect.gui import theme as _theme
from streamselect.gui import theme_palettes
from streamselect.gui.token_color import to_qcolor

_SWATCH = QSize(44, 26)


def swatch(name: str) -> QPixmap:
    """A small window in theme *name*'s colours: its background, a card on it,
    a line of text and the accent."""
    p = theme_palettes.PALETTES[name]
    pix = QPixmap(_SWATCH)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(to_qcolor(p["COLOR_BORDER"]))
    painter.setBrush(to_qcolor(p["COLOR_BG_DEEP"]))
    painter.drawRoundedRect(QRectF(0.5, 0.5, _SWATCH.width() - 1, _SWATCH.height() - 1), 4, 4)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(to_qcolor(p["COLOR_BG_CARD"]))
    painter.drawRoundedRect(QRectF(5, 5, 22, _SWATCH.height() - 10), 2, 2)
    painter.setBrush(to_qcolor(p["COLOR_TEXT_HI"]))
    painter.drawRect(QRectF(8, 9, 15, 2))
    painter.setBrush(to_qcolor(p["COLOR_TEXT"]))
    painter.drawRect(QRectF(8, 14, 11, 2))
    painter.setBrush(to_qcolor(p["COLOR_ACCENT"]))
    painter.drawEllipse(QRectF(31, 8, 9, 9))
    painter.end()
    return pix


class ThemeList(QWidget):
    """One row per theme; the current one is checked. Emits ``picked``."""

    picked = pyqtSignal(str)

    def __init__(self, current: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 4, 0, 0)
        box.setSpacing(4)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for name in _theme.available_themes():
            row = QPushButton(name)
            row.setObjectName(f"tourTheme_{name}")
            row.setCheckable(True)
            row.setChecked(name == current)
            row.setIcon(QIcon(swatch(name)))
            row.setIconSize(_SWATCH)
            row.setToolTip(f"Switch to the {name} theme")
            _theme.style(row, "TOUR_THEME_ROW")
            row.clicked.connect(lambda _c=False, n=name: self.picked.emit(n))
            self._group.addButton(row)
            box.addWidget(row)

    def checked(self) -> str:
        button = self._group.checkedButton()
        return button.text() if button is not None else ""
