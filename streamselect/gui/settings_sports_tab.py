"""Settings ▸ Sports: each sport's game timings (design "Sports Settings" rev 1,
SS-Q1–Q11, owner 2026-11-18).

One page per dialog, a picker at the top: **All sports** (values for every sport
that sets none of its own, owner 2026-11-18), then each sport. A setting shows only
where it may be set (``tuning.Spec.scope``): game length per sport, "Most watched"
and the clocks for all sports, the rest at both. Only values the user SETS are
stored — set equal to the default, it is still theirs — and a row the user set
shows its default (or "set by you") and a Reset; a sport's row that follows All
sports says so. Advanced (how games are found) starts collapsed.

The page edits a working copy of ``Config.sport_settings_overrides``; the dialog
calls :meth:`SportsSettingsPage.load` and :meth:`SportsSettingsPage.save`.
"""

from __future__ import annotations

import copy
from typing import Optional

from PyQt6.QtCore import QTime, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QTimeEdit, QToolButton, QVBoxLayout, QWidget,
)

from streamselect.core.games import tuning
from streamselect.core.games.store import sport_settings
from streamselect.gui import cursor_affordance
from streamselect.gui import icon_utils as _icon_utils
from streamselect.gui import theme as _theme

#: The Settings page's help text (the dialog's right-hand column).
SPORTS_HELP = (
    "How long each sport's games run, which games are listed, and how alerts and viewing "
    "are counted. All sports sets a value for every sport; a sport can set its own. Every "
    "value starts at a measured default; one you set shows its default and a Reset beside "
    "it, and stays as you set it when a default changes later.")


#: The label column's widest: a longer label wraps rather than widening every row.
_LABEL_MAX_W = 230


class _Row:
    """One setting's controls: the value, a note ("default 2 h 45 min" / "set by you"), Reset."""

    def __init__(self, spec: tuning.Spec):
        self.spec = spec
        if spec.unit == "hm":
            self.editor = QTimeEdit()
            self.editor.setDisplayFormat("H 'h' mm 'min'")
            self.editor.setMinimumTime(QTime(spec.lo // 60, spec.lo % 60))
            self.editor.setMaximumTime(QTime(min(spec.hi // 60, 23), spec.hi % 60 if spec.hi < 1440 else 59))
        else:
            self.editor = QSpinBox()
            self.editor.setRange(spec.lo, spec.hi)
            self.editor.setSuffix(spec.suffix)
        self.editor.setToolTip(spec.tip)
        self.note = QLabel()
        _theme.style(self.note, "TEXT_SM_MUTED")
        self.reset = QPushButton("Reset")
        self.reset.setFlat(True)
        _theme.style(self.reset, "LINK_BTN_SM")
        _icon_utils.set_button_icon(self.reset, "undo")
        cursor_affordance.set_clickable(self.reset)
        # Which setting a signal came from (the page connects bound methods, which
        # PyQt holds weakly; a lambda here held the page in a cycle past its dialog).
        for w in (self.editor, self.reset):
            w.setProperty("tuningKey", spec.key)
        # The value on one line, its note and Reset on a second beneath it: side by side
        # they made each row ~620 px, wider than the page has (owner, 2026-11-22).
        self.box = QWidget()
        v = QVBoxLayout(self.box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        line = QHBoxLayout()
        line.addWidget(self.editor)
        line.addStretch(1)
        v.addLayout(line)
        self.extra = QWidget()
        h = QHBoxLayout(self.extra)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        h.addWidget(self.note)
        h.addWidget(self.reset)
        h.addStretch(1)
        v.addWidget(self.extra)

    def value(self) -> int:
        if isinstance(self.editor, QTimeEdit):
            t = self.editor.time()
            return t.hour() * 60 + t.minute()
        return self.editor.value()

    def show_value(self, value: int) -> None:
        self.editor.blockSignals(True)
        if isinstance(self.editor, QTimeEdit):
            self.editor.setTime(QTime(value // 60, value % 60))
        else:
            self.editor.setValue(value)
        self.editor.blockSignals(False)

    def show_choice(self, mine: Optional[list], default: int, follows: Optional[int] = None) -> None:
        """A value the user set shows its default (or that it is theirs) and a Reset;
        a sport's value that follows the All sports choice (*follows*) says so."""
        if mine is None:
            self.note.setText("from All sports" if follows is not None else "")
            self.note.setToolTip("Set under All sports; set it here to give this sport its own"
                                 if follows is not None else "")
            self.note.setVisible(follows is not None)
            self.reset.hide()
            self.extra.setVisible(follows is not None)
            return
        self.note.setToolTip("")
        self.note.setText("set by you" if int(mine[0]) == default else f"default {self.spec.text(default)}")
        self.note.show()
        self.reset.setToolTip(f"Back to the default, {self.spec.text(default)}, and follow it from now on")
        self.reset.show()
        self.extra.show()


class SportsSettingsPage(QWidget):
    """The Sports page. Builds without a config; :meth:`load` fills it."""

    #: The user changed a game's length (usual or longest): its row, for a first-time tip.
    lengthEdited = pyqtSignal(QWidget)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._overrides: dict = {}
        self._sports = [tuning.ALL, *sport_settings()]
        self._sport = tuning.ALL
        self.rows: dict[str, _Row] = {}

        lay = QVBoxLayout(self)
        lay.setSpacing(14)
        lay.setContentsMargins(12, 12, 12, 12)
        top = QHBoxLayout()
        top.addWidget(QLabel("Sport:"))
        self.sport_combo = QComboBox()
        for sport in self._sports:
            self.sport_combo.addItem(tuning.sport_label(sport), sport)
        self.sport_combo.setToolTip("All sports sets values for every sport; pick a sport to "
                                    "give it its own")
        self.sport_combo.currentIndexChanged.connect(self._on_sport)
        top.addWidget(self.sport_combo)
        top.addStretch(1)
        self.reset_all = QPushButton()
        _theme.style(self.reset_all, "RECIPE_CLEAR_BTN")
        cursor_affordance.set_clickable(self.reset_all)
        self.reset_all.clicked.connect(self._reset_sport)
        top.addWidget(self.reset_all)
        lay.addLayout(top)
        hint = QLabel("A sport's own value wins over All sports.")
        hint.setWordWrap(True)
        _theme.style(hint, "TEXT_SM_MUTED")
        lay.addWidget(hint)

        forms: dict[str, QFormLayout] = {}
        self._boxes: dict[str, QGroupBox] = {}
        self._forms = forms
        for group in tuning.GROUPS:
            box = QGroupBox("" if group == tuning.ADVANCED else group)
            form = QFormLayout(box)
            form.setSpacing(8)
            forms[group] = form
            self._boxes[group] = box
            if group == tuning.ADVANCED:
                self.advanced_toggle = QToolButton()
                self.advanced_toggle.setText(group)
                self.advanced_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                cursor_affordance.set_clickable(self.advanced_toggle)
                self.advanced_toggle.clicked.connect(self._toggle_advanced)
                lay.addWidget(self.advanced_toggle)
                why = QLabel("These decide which listings are one game. The defaults were measured "
                             "on real listings; change them only to fix a sport the defaults get wrong.")
                why.setWordWrap(True)
                _theme.style(why, "TEXT_SM_MUTED")
                form.addRow(why)
                self.advanced_box = box
            lay.addWidget(box)
            if group == tuning.ALERTS:
                lead = QLabel("How early an alert notifies is on the Watch Alerts page.")
                lead.setWordWrap(True)
                _theme.style(lead, "TEXT_SM_MUTED")
                self._alerts_form = form
        for spec in tuning.SPECS:
            row = _Row(spec)
            if isinstance(row.editor, QTimeEdit):
                row.editor.timeChanged.connect(self._on_edit)
            else:
                row.editor.valueChanged.connect(self._on_edit)
            row.reset.clicked.connect(self._on_reset)
            label = QLabel(spec.label)
            label.setWordWrap(True)        # a long Advanced label must not set the column
            label.setMaximumWidth(_LABEL_MAX_W)
            forms[spec.group].addRow(label, row.box)
            self.rows[spec.key] = row
        self._alerts_form.addRow("", lead)

        self.ask_check = QCheckBox("Tell me when a default I changed is improved")
        self.ask_check.setToolTip("After an update, ask whether to keep your value or take the "
                                  "improved default. Off: keep yours and never ask.")
        lay.addWidget(self.ask_check)
        lay.addStretch(1)
        self._set_advanced(False)
        self._show()

    # ── the dialog's load/save ────────────────────────────────────────────
    def load(self, config) -> None:
        self._overrides = copy.deepcopy(dict(config.sport_settings_overrides or {}))
        self.ask_check.setChecked(bool(config.ask_about_improved_defaults))
        self._show()

    def save(self, config) -> None:
        config.sport_settings_overrides = copy.deepcopy(self._overrides)
        config.ask_about_improved_defaults = self.ask_check.isChecked()

    # ── editing ───────────────────────────────────────────────────────────
    def _show(self) -> None:
        """Every row from the current sport's values and the user's choices."""
        vals = tuning.values(self._sport, self._overrides)
        defs = tuning.defaults(self._sport)
        mine = tuning.chosen(self._overrides, self._sport)
        follows = tuning.inherited(self._sport, self._overrides)
        for key, row in self.rows.items():
            here = row.spec.settable_for(self._sport)
            self._forms[row.spec.group].setRowVisible(row.box, here)
            row.show_value(vals[key])
            row.show_choice(mine.get(key), defs[key], follows.get(key))
        # A group with nothing settable here (game length under All sports) goes.
        for group, box in self._boxes.items():
            if group != tuning.ADVANCED:
                box.setVisible(any(r.spec.settable_for(self._sport)
                                   for r in self.rows.values() if r.spec.group == group))
        label = tuning.sport_label(self._sport)
        self.reset_all.setText(f"Reset {label} to defaults")
        self.reset_all.setEnabled(bool(mine))
        self.reset_all.setToolTip(f"Every {label} value back to its default")

    def _sender_row(self) -> Optional[_Row]:
        sender = self.sender()
        return self.rows.get(sender.property("tuningKey")) if sender is not None else None

    def _on_edit(self, *_args) -> None:
        """A value the user set is theirs, even when it equals the default (owner)."""
        row = self._sender_row()
        if row is not None:
            self.edit(row.spec.key, row.value())
            if row.spec.key in ("usual_length", "long_limit"):
                self.lengthEdited.emit(row.box)

    def _on_reset(self, *_args) -> None:
        row = self._sender_row()
        if row is not None:
            self.reset_one(row.spec.key)

    def edit(self, key: str, value: int) -> None:
        """Store *value* as the user's choice for *key* (what an edit in the row does)."""
        tuning.set_choice(self._overrides, self._sport, key, value)
        self._show()

    def reset_one(self, key: str) -> None:
        """Forget the user's choice for *key*: it follows the defaults again."""
        tuning.reset(self._overrides, self._sport, key)
        self._show()

    def _reset_sport(self) -> None:
        tuning.reset(self._overrides, self._sport)
        self._show()

    def select_sport(self, sport: str) -> None:
        """Show *sport*'s values (or :data:`tuning.ALL`'s)."""
        self.sport_combo.setCurrentIndex(max(0, self.sport_combo.findData(sport)))

    def _on_sport(self, _index: int) -> None:
        self._sport = self.sport_combo.currentData() or self._sport
        self._show()

    def _toggle_advanced(self) -> None:
        self._set_advanced(self.advanced_box.isHidden())

    def _set_advanced(self, open_: bool) -> None:
        self.advanced_box.setVisible(open_)
        _icon_utils.set_button_icon(self.advanced_toggle, "collapse" if open_ else "expand")
        self.advanced_toggle.setToolTip("Collapse the advanced settings" if open_
                                        else "Expand the advanced settings")
