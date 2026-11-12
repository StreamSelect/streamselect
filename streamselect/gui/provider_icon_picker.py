"""The source icon picker: a colour-circle palette plus a custom emoji.

Used on the Summary tab of the Sources editor, while adding a source as well
as while editing one.
"""
from __future__ import annotations

from typing import List

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from streamselect.gui import icon_utils as _icon_utils
from streamselect.gui import icons as _icons
from streamselect.gui import theme as _theme


class ProviderIconPicker(QWidget):
    """Icon display that reveals a colored-circle palette when clicked."""

    icon_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._icon = ""
        self._color_btns: List[tuple] = []
        self._setup()

    def _setup(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._btn = QPushButton()
        _icon_utils.set_button_icon(self._btn, "provider")
        self._btn.setFixedSize(48, 48)
        _theme.style(self._btn, "ICON_PICK_MAIN_BTN")
        self._btn.setToolTip("Click to change icon")
        self._btn.clicked.connect(self._toggle_palette)
        layout.addWidget(self._btn)

        self._palette = QFrame()
        _theme.style(self._palette, "ICON_PICK_POPUP")
        self._palette.hide()
        pal_layout = QVBoxLayout(self._palette)
        pal_layout.setContentsMargins(8, 8, 8, 8)
        pal_layout.setSpacing(6)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(3)
        for icon in _icons.provider_icon_palette:
            b = QPushButton(icon)
            b.setFixedSize(30, 30)
            b.setToolTip(f"Use {icon} as this source's mark")
            _theme.style(b, "ICON_PICK_BTN")
            b.clicked.connect(lambda checked, i=icon: self._pick(i))
            btn_row.addWidget(b)
            self._color_btns.append((icon, b))
        btn_row.addStretch()
        pal_layout.addLayout(btn_row)

        custom_row = QHBoxLayout()
        self._custom_label = QLabel("Custom:")
        _theme.style_fn(self._custom_label, lambda: f"font-size: {_theme.FONT_MD}; color: {_theme.COLOR_TEXT};")
        custom_row.addWidget(self._custom_label)
        self._custom_input = QLineEdit()
        self._custom_input.setClearButtonEnabled(True)
        self._custom_input.setPlaceholderText("emoji…")
        self._custom_input.setFixedWidth(80)
        self._custom_input.setMaxLength(8)
        _theme.style_fn(self._custom_input, lambda: f"font-size: {_theme.FONT_INPUT};")
        custom_row.addWidget(self._custom_input)
        apply_btn = QPushButton("Apply")
        apply_btn.setFixedWidth(54)
        apply_btn.setToolTip("Use the emoji typed here as this source's mark")
        apply_btn.clicked.connect(self._apply_custom)
        custom_row.addWidget(apply_btn)
        custom_row.addStretch()
        pal_layout.addLayout(custom_row)

        layout.addWidget(self._palette)

    def _toggle_palette(self):
        self._palette.setVisible(not self._palette.isVisible())

    def _pick(self, icon: str):
        self._icon = icon
        self._btn.setText(icon)
        self._palette.hide()
        self._update_selection(icon)
        self.icon_changed.emit(icon)

    def _apply_custom(self):
        text = self._custom_input.text().strip()
        if text:
            self._pick(text)

    def _update_selection(self, selected: str):
        for icon, btn in self._color_btns:
            _theme.style(
                btn,
                "ICON_PICK_BTN_SELECTED" if icon == selected else "ICON_PICK_BTN",
            )

    def get_icon(self) -> str:
        return self._icon

    def set_icon(self, icon: str):
        self._icon = icon
        # A chosen emoji is the user's own mark (F43) and stays text; with
        # none chosen the button shows the default provider icon.
        self._btn.setText(icon)
        if icon:
            _icon_utils.clear_button_icon(self._btn)
        else:
            _icon_utils.set_button_icon(self._btn, "provider")
        self._update_selection(icon)

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        self._btn.setEnabled(enabled)
