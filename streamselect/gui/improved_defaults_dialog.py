""""Some defaults were improved": shown once after an update moved a default the
user had set (design "Sports Settings" SS-Q8/Q9, owner 2026-11-18).

Built like the "New filter values" dialog (``new_facet_values_dialog.py``). Only
settings the user set are listed — everything else already follows the new
default. Each row starts on "keep yours"; Apply takes the rows switched to the new
default, "Keep all mine" changes nothing, and the checkbox stops the prompt for good.
Whatever is answered, each listed change is not asked about again.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QDialog, QDialogButtonBox, QGridLayout, QLabel, QRadioButton,
    QVBoxLayout, QWidget,
)

from streamselect.core.games import tuning
from streamselect.gui import icon_utils as _icon_utils
from streamselect.gui import theme as _theme
from streamselect.gui.dialog_chrome import dialog_buttons


class ImprovedDefaultsDialog(QDialog):
    """Keep yours or take the new default, per setting.

    Args:
        items: the stored choices whose default moved (``tuning.improved``).
    """

    def __init__(self, items: list[tuning.Improved], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.items = list(items)
        self.setWindowTitle("Improved Defaults")
        self.setMinimumWidth(560)
        vl = QVBoxLayout(self)
        vl.setSpacing(10)
        head = QLabel(f"{_icon_utils.role_html('info')}&nbsp;Some defaults were improved")
        _theme.style_fn(head, lambda: f"font-size: {_theme.FONT_XL}; font-weight: bold; color: {_theme.COLOR_TEXT};")
        vl.addWidget(head)
        hint = QLabel("This update changed defaults for settings you had set yourself. Values you "
                      "never changed already use the new defaults. For each of these, keep yours or "
                      "take the new one.")
        hint.setWordWrap(True)
        _theme.style_fn(hint, lambda: f"font-size: {_theme.FONT_MD}; color: {_theme.COLOR_TEXT};")
        vl.addWidget(hint)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(6)
        for col, title in ((1, "Yours"), (2, "New default")):
            lb = QLabel(title.upper())
            _theme.style_fn(lb, lambda: f"font-size: {_theme.FONT_SM}; font-weight: bold; "
                            f"color: {_theme.COLOR_MUTED_2}; letter-spacing: 1px;")
            grid.addWidget(lb, 0, col)
        self.take: list[QRadioButton] = []
        for r, item in enumerate(self.items, start=1):
            spec = tuning.BY_KEY[item.key]
            grid.addWidget(QLabel(f"<b>{item.sport.title()}</b> · {spec.label.rstrip(':')}"), r, 0)
            keep = QRadioButton(spec.text(item.yours))
            keep.setToolTip("Keep your value")
            new = QRadioButton(spec.text(item.new))
            new.setToolTip(f"Take the new default (it was {spec.text(item.was)})")
            keep.setChecked(True)
            group = QButtonGroup(self)
            group.addButton(keep)
            group.addButton(new)
            grid.addWidget(keep, r, 1)
            grid.addWidget(new, r, 2)
            was = QLabel(f"was {spec.text(item.was)}")
            _theme.style(was, "TEXT_SM_MUTED")
            grid.addWidget(was, r, 3)
            self.take.append(new)
        vl.addLayout(grid)

        self.never = QCheckBox("Don't ask me about improved defaults again (keep my values)")
        vl.addWidget(self.never)
        buttons = dialog_buttons(self, ok="Apply")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setToolTip(
            "Take the new defaults you picked; keep the rest of yours")
        mine = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        mine.setText("Keep all mine")
        mine.setToolTip("Keep every value you set")
        vl.addWidget(buttons)

    def apply_to(self, overrides: dict, accepted: bool) -> None:
        """Record the answer in *overrides*: taken rows follow the defaults again; the
        rest keep the user's value and note the new default, so none is asked again."""
        for item, new in zip(self.items, self.take):
            if accepted and new.isChecked() and not self.never.isChecked():
                tuning.take_new(overrides, item)
            else:
                tuning.keep_mine(overrides, item)
