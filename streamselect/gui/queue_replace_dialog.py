"""The Watch Queue's "Replace unavailable items…" window.

Lists queue items on sources that cannot play, each beside the copy that would
replace it — ``[queued copy] → [copy on an active source]`` — so the user sees
exactly what changes and unticks what they want kept (owner, 2026-11-17). The
work is ``core/queue_replacement.py``; this is the window and the hand-off:
:func:`open_queue_replace` reads off the UI thread, and the swap ends in an
Undo toast rather than a confirmation.

As non-destructive as it can be (owner): rows come in three groups, each
group's own tick box selecting or clearing all of it —

- **Ready to replace**: same title by TMDb id, same language. Ticked.
- **Check these first**: a doubt (``Stranded.doubts``: another language, or a
  match on the name alone), said in the Note column. Unticked.
- **Already in your queue**: the title is queued from an active source too
  (owner's "Alien: Earth"), so this copy is a duplicate. Greyed, never swapped.
- **Nothing to replace them**: greyed, with the reason, and left in the queue.

A trash button at the far right of every row and group header — shown only
on the row under the mouse, which is lightly highlighted, or on a struck row —
strikes rows through: struck rows are not migrated but removed from the queue on Replace,
and clicking it again keeps them (owner, 2026-11-17).

A row with several copies has a drop-down. Nothing changes until Replace,
which keeps the window open: the swapped rows drop out and the doubtful ones
move up to be checked next (owner). Each Replace gets its own Undo, and what is
left can be revisited from the same menu any time.
"""

from __future__ import annotations

from loguru import logger
from PyQt6.QtCore import QEvent, QSize, Qt
from PyQt6.QtGui import QBrush, QColor, QCursor
from PyQt6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QRadioButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from streamselect.core.queue_replacement import (
    SCOPE_ALL, SCOPE_EXPIRED, Copy, Stranded, find_stranded, replace, undo,
)
from streamselect.gui import icon_utils as _icon_utils
from streamselect.gui import theme as _theme
from streamselect.gui.dialog_chrome import dialog_buttons

COL_OLD, COL_ARROW, COL_NEW, COL_NOTE, COL_REMOVE = 0, 1, 2, 3, 4
GROUP_SURE, GROUP_CHECK = "Ready to replace", "Check these first"
GROUP_DUPLICATE, GROUP_NONE = "Already in your queue", "Nothing to replace them"
REMOVING_NOTE = "Will be removed from your queue"
_STATE_WORDS = {"expired": "expired", "disabled": "switched off", "removed": "removed"}


def describe(copy: Copy) -> str:
    """One copy as a row reads it: "EN · Dark Matter (2024) · 4K · Source"."""
    title = f"{copy.title} ({copy.year})" if copy.year and copy.year not in copy.title else copy.title
    return " · ".join(p for p in (copy.language, title, copy.quality, copy.source) if p)


def describe_new(copy: Copy) -> str:
    """A replacement copy, marked when its language differs from the queued one."""
    return describe(copy) + ("" if copy.same_language else "  · other language")


class QueueReplaceDialog(QDialog):
    """Review and tick the swaps; :meth:`choices` is what is ticked now."""

    def __init__(self, stranded: list[Stranded], parent=None, on_replace=None):
        """*on_replace* gets the ticked ``(queue_id, channel_id)`` pairs; the
        window stays open, and the caller hands back the new list via
        :meth:`reload` (owner: replace the sure ones, then the doubtful ones
        move up to be checked)."""
        super().__init__(parent)
        self._on_replace = on_replace
        self.setWindowTitle("Replace unavailable items")
        self.resize(1100, 640)
        self._all = stranded
        self._rows: list[tuple[Stranded, QTreeWidgetItem, QComboBox | None]] = []
        self.groups: dict[str, QTreeWidgetItem] = {}
        self.removing: set[int] = set()          # queue ids struck through
        self._row_of: dict[int, tuple[Stranded, QTreeWidgetItem, QComboBox | None]] = {}
        self._remove_btn: dict[int, QPushButton] = {}
        self._notes: dict[int, str] = {}
        self._trash_of: dict[int, QPushButton] = {}   # id(item) -> its trash button
        self._items: dict[int, QTreeWidgetItem] = {}  # id(item) -> item (rows and headers)
        self._hover: QTreeWidgetItem | None = None

        layout = QVBoxLayout(self)
        intro = QLabel("These Watch Queue items are on sources that can't play. Ticked items are "
                       "swapped for the same title on an active source; each keeps its place in "
                       "the queue, and its watch history moves with it.")
        intro.setWordWrap(True)
        _theme.style(intro, "PANEL_BODY")
        layout.addWidget(intro)

        scope_row = QHBoxLayout()
        self._scope = QButtonGroup(self)
        self.expired_only = QRadioButton("Expired sources")
        self.everything = QRadioButton("Expired, switched-off and removed sources")
        self.expired_only.setToolTip("Only items whose source's subscription has ended")
        self.everything.setToolTip("Also items on sources you switched off or removed")
        for b in (self.expired_only, self.everything):
            self._scope.addButton(b)
            scope_row.addWidget(b)
        scope_row.addStretch(1)
        self.expired_only.setChecked(True)
        self._scope.buttonToggled.connect(lambda _b, on: on and self._fill())
        layout.addLayout(scope_row)

        self.summary = QLabel()
        _theme.style(self.summary, "PANEL_BODY")
        layout.addWidget(self.summary)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(["In your queue", "", "Replace with", "Note", ""])
        self.tree.setUniformRowHeights(True)
        # Every row, header or not, gets this height. With uniform heights the
        # list sizes all rows by the FIRST one, and a header (text only) made
        # every row 17 px under 25 px drop-downs after a scope switch (owner's
        # "smooshed" rows); hovering re-laid it out, which hid the cause.
        self._row_size = QSize(0, max(QComboBox().sizeHint().height(), 24) + 2)   # 0: a -1 width is an invalid size Qt ignores
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(COL_OLD, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_ARROW, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COL_NEW, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_NOTE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_REMOVE, QHeaderView.ResizeMode.Fixed)
        self.tree.setColumnWidth(COL_ARROW, 28)
        self.tree.setColumnWidth(COL_REMOVE, 30)
        self.tree.itemChanged.connect(lambda *_: self._update_count())
        # Trash buttons show only on the row under the mouse (owner: "otherwise
        # it's just a messy row of trash"), which is also lightly highlighted.
        self.tree.setMouseTracking(True)
        self.tree.viewport().installEventFilter(self)
        layout.addWidget(self.tree, 1)

        self.buttons = dialog_buttons(self, ok="Replace", on_ok=self._replace)
        self._ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Close")
        layout.addWidget(self.buttons)
        self._fill()

    @property
    def scope(self) -> str:
        return SCOPE_EXPIRED if self.expired_only.isChecked() else SCOPE_ALL

    def shown(self) -> list[Stranded]:
        return [s for s in self._all if self.scope == SCOPE_ALL or s.state == "expired"]

    def _group(self, title: str, rows: list[Stranded], checkable: bool) -> QTreeWidgetItem | None:
        if not rows:
            return None
        group = QTreeWidgetItem([f"{title} ({len(rows)})"])
        group.setSizeHint(COL_OLD, self._row_size)
        font = group.font(COL_OLD)
        font.setBold(True)
        group.setFont(COL_OLD, font)
        flags = Qt.ItemFlag.ItemIsEnabled
        if checkable:
            flags |= Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate
            group.setToolTip(COL_OLD, f"Tick or clear every item under {title}")
        group.setFlags(flags)
        self.tree.addTopLevelItem(group)
        self.groups[title] = group
        ids = [s.queue_id for s in rows]
        btn = self._trash(f"Remove every item under {title} from your queue, or keep them all",
                          lambda: self._strike_all(ids))
        btn.setCheckable(False)
        self._attach_trash(group, btn)
        return group

    def _attach_trash(self, item: QTreeWidgetItem, btn: QPushButton) -> None:
        # In a holder: the view re-shows its cell widgets on every layout, so a
        # hidden button set as the cell widget would come straight back.
        holder = QWidget()
        box = QHBoxLayout(holder)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(btn)
        holder.installEventFilter(self)
        self.tree.setItemWidget(item, COL_REMOVE, holder)
        self._trash_of[id(item)] = btn
        self._items[id(item)] = item
        btn.installEventFilter(self)
        btn.setVisible(False)

    def eventFilter(self, obj, event):  # noqa: N802 — Qt override
        """Follow the mouse: over the list, over a row's own widgets, or out."""
        kind = event.type()
        if obj is self.tree.viewport() and kind == QEvent.Type.MouseMove:
            self._set_hover(self.tree.itemAt(event.position().toPoint()))
        elif kind in (QEvent.Type.Enter, QEvent.Type.Leave):
            pos = self.tree.viewport().mapFromGlobal(QCursor.pos())
            inside = self.tree.viewport().rect().contains(pos)
            self._set_hover(self.tree.itemAt(pos) if inside else None)
        return False

    def _set_hover(self, item: QTreeWidgetItem | None) -> None:
        if item is not None and id(item) not in self._trash_of:
            item = None
        if item is self._hover:
            return
        previous, self._hover = self._hover, item
        for it in (previous, item):
            if it is not None:
                self._paint_hover(it)

    def _paint_hover(self, item: QTreeWidgetItem) -> None:
        on = item is self._hover
        brush = QBrush(QColor(_theme.COLOR_LINE_DARK)) if on else QBrush()
        for col in range(self.tree.columnCount()):
            item.setBackground(col, brush)
        btn = self._trash_of[id(item)]
        btn.setVisible(on or btn.isChecked())     # a struck row keeps its button, to undo it

    def _trash(self, tip: str, on_click) -> QPushButton:
        btn = QPushButton()
        _icon_utils.set_button_icon(btn, "delete", color=_theme.COLOR_TEXT)
        btn.setFixedSize(22, 20)          # structural — matches the sidebar's PANEL_BTN peers
        btn.setFlat(True)
        btn.setCheckable(True)
        btn.setToolTip(tip)
        _theme.style(btn, "PANEL_BTN")
        btn.clicked.connect(lambda *_: on_click())
        return btn

    def _fill(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        self._rows, self.groups, self._row_of, self._remove_btn, self._notes = [], {}, {}, {}, {}
        self._trash_of, self._items, self._hover = {}, {}, None
        shown = self.shown()
        self.removing &= {s.queue_id for s in shown}
        sure = [s for s in shown if s.best is not None and not s.doubts]
        check = [s for s in shown if s.best is not None and s.doubts]
        dupes = [s for s in shown if s.best is None and s.duplicate]
        none = [s for s in shown if s.best is None and not s.duplicate]
        arrow = _icon_utils.role_icon("replace_with", _theme.COLOR_MUTED)
        muted = QBrush(QColor(_theme.COLOR_MUTED))
        for title, rows, ticked in ((GROUP_SURE, sure, True), (GROUP_CHECK, check, False),
                                    (GROUP_DUPLICATE, dupes, None), (GROUP_NONE, none, None)):
            group = self._group(title, rows, checkable=ticked is not None)
            for s in rows:
                old = f"{describe(s.old)} · {_STATE_WORDS.get(s.state, s.state)}"
                item = QTreeWidgetItem([old, "", "", ""])
                item.setSizeHint(COL_OLD, self._row_size)
                item.setToolTip(COL_OLD, old)
                group.addChild(item)
                combo = None
                if s.best is None:
                    item.setFlags(Qt.ItemFlag.ItemIsSelectable)      # shown, greyed, left alone
                    item.setText(COL_NOTE, s.reason)
                    for col in (COL_OLD, COL_NOTE):
                        item.setForeground(col, muted)
                else:
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(COL_OLD, Qt.CheckState.Checked if ticked
                                       else Qt.CheckState.Unchecked)
                    item.setIcon(COL_ARROW, arrow)
                    note = "; ".join(s.doubts)
                    item.setText(COL_NOTE, note[:1].upper() + note[1:])
                    if len(s.candidates) > 1:
                        combo = QComboBox()
                        combo.setToolTip(f"{len(s.candidates)} copies on your active sources: "
                                         "pick one")
                        for c in s.candidates:
                            combo.addItem(describe_new(c), c.channel_id)
                        self.tree.setItemWidget(item, COL_NEW, combo)
                        combo.installEventFilter(self)    # the mouse over a row's drop-down
                    else:
                        item.setText(COL_NEW, describe_new(s.best))
                        item.setToolTip(COL_NEW, item.text(COL_NEW))
                self._rows.append((s, item, combo))
                self._row_of[s.queue_id] = (s, item, combo)
                self._notes[s.queue_id] = item.text(COL_NOTE)
                btn = self._trash("Remove this item from your queue instead of replacing it "
                                  "(click again to keep it)",
                                  lambda q=s.queue_id: self._strike(q, q not in self.removing))
                self._remove_btn[s.queue_id] = btn
                self._attach_trash(item, btn)
                if s.queue_id in self.removing:
                    self._strike(s.queue_id, True, update=False)
            if group is not None:
                group.setExpanded(True)
        self.tree.blockSignals(False)
        self._update_count()

    def _strike(self, queue_id: int, on: bool, update: bool = True) -> None:
        """Strike a row through (removed on Replace, never migrated) or keep it."""
        s, item, combo = self._row_of[queue_id]
        self.tree.blockSignals(True)
        (self.removing.add if on else self.removing.discard)(queue_id)
        for col in (COL_OLD, COL_NEW, COL_NOTE):
            font = item.font(col)
            font.setStrikeOut(on)
            item.setFont(col, font)
        if combo is not None:
            combo.setEnabled(not on)
            f = combo.font()
            f.setStrikeOut(on)
            combo.setFont(f)
        if s.best is not None:
            if on:
                item.setCheckState(COL_OLD, Qt.CheckState.Unchecked)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            else:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setText(COL_NOTE, REMOVING_NOTE if on else self._notes[queue_id])
        self._remove_btn[queue_id].setChecked(on)
        self._paint_hover(item)
        self.tree.blockSignals(False)
        if update:
            self._update_count()

    def _strike_all(self, ids: list[int]) -> None:
        on = not all(q in self.removing for q in ids)
        for q in ids:
            self._strike(q, on, update=False)
        self._update_count()

    def removals(self) -> list[int]:
        """Queue ids struck through, to remove rather than migrate."""
        return [s.queue_id for s, _i, _c in self._rows if s.queue_id in self.removing]

    def _replace(self) -> None:
        picked, removed = self.choices(), self.removals()
        if (picked or removed) and self._on_replace is not None:
            self._on_replace(picked, removed)

    def reload(self, stranded: list[Stranded]) -> None:
        """Show a fresh scan, after a Replace or an Undo, keeping the scope."""
        self._all = stranded
        self._fill()

    def choices(self) -> list[tuple[int, str]]:
        """``(queue_id, channel_id)`` for every ticked row, with its picked copy."""
        out = []
        for s, item, combo in self._rows:
            if (s.best is None or s.queue_id in self.removing
                    or item.checkState(COL_OLD) != Qt.CheckState.Checked):
                continue
            out.append((s.queue_id, combo.currentData() if combo is not None else s.best.channel_id))
        return out

    def _update_count(self) -> None:
        shown = [s for s, _i, _c in self._rows]
        ticked, struck = len(self.choices()), len(self.removals())
        if not shown:
            self.summary.setText("Nothing to replace: every queued item in this group is on an "
                                 "active source.")
        else:
            gone = f" · {struck} to remove" if struck else ""
            self.summary.setText(f"{len(shown)} unavailable · {ticked} ticked to replace{gone}. "
                                 "Anything else stays as it is, and you can come back to it "
                                 "from the same menu.")
        if self._ok is not None:
            parts = ([f"Replace {ticked}"] if ticked else []) + ([f"Remove {struck}"] if struck else [])
            self._ok.setText(" · ".join(parts) or "Replace")
            self._ok.setEnabled(bool(ticked or struck))


def open_queue_replace(host, section) -> None:
    """Read the unavailable items off the UI thread, then show the window.

    *host* is the main window: ``_run_query``, ``db``, ``config``,
    ``notification_manager``, ``status``, ``load_history``.
    """
    def scan(then) -> None:
        host._run_query(lambda repos: find_stranded(repos, SCOPE_ALL, host.config), then,
                        on_error=lambda e: host.status(f"Couldn't read the queue: {e}", ms=0,
                                                       level="error"))

    def show(stranded) -> None:
        if not stranded:
            host.status("Every Watch Queue item is on an active source", ms=0)
            return
        dialog = QueueReplaceDialog(stranded, host)

        def rescan() -> None:
            try:
                if dialog.isVisible():
                    scan(dialog.reload)
            except RuntimeError:
                pass                       # the window was closed and deleted

        dialog._on_replace = lambda picked, removed: apply_replacements(
            host, section, picked, rescan, removals=removed)
        dialog.exec()

    scan(show)


def apply_replacements(host, section, choices: list[tuple[int, str]], after=None,
                       removals: list[int] = ()) -> None:
    """Swap the chosen items, remove the struck ones, refresh, and offer Undo.
    *after* runs after both the change and an Undo (the open window re-reads)."""
    if not choices and not removals:
        return
    try:
        with host.db.session_scope() as session:
            outcome = replace(session, choices, removals)
            done, skipped, snapshot = outcome.replaced, outcome.skipped, outcome.snapshot
    except Exception as e:  # noqa: BLE001 — a failed swap must not crash the window
        logger.error(f"Replacing queue items failed: {e}")
        host.status(f"Couldn't replace queue items: {e}", ms=0, level="error")
        return
    _refresh(host, section)
    if after is not None:
        after()
    gone = outcome.removed
    did = " and ".join(p for p in (f"replaced {done}" if done else "",
                                   f"removed {gone}" if gone else "") if p)
    note = f" {skipped} already in the queue were left as they were." if skipped else ""
    logger.info("Watch Queue: replaced {}, removed {} unavailable item(s), {} skipped",
                done, gone, skipped)
    host.status(f"Watch Queue: {did} item(s)", ms=0)
    host.notification_manager.show(
        title="Watch Queue updated",
        message=f"{did[:1].upper() + did[1:]} unavailable item(s).{note}",
        type="info", auto_dismiss_ms=12000,
        actions=[("Undo", lambda: undo_replacements(host, section, snapshot, after))])


def undo_replacements(host, section, snapshot, after=None) -> None:
    try:
        with host.db.session_scope() as session:
            restored = undo(session, snapshot)
    except Exception as e:  # noqa: BLE001 — the toast's callback must not raise
        logger.error(f"Undoing queue replacement failed: {e}")
        host.status(f"Couldn't undo: {e}", ms=0, level="error")
        return
    _refresh(host, section)
    if after is not None:
        after()
    host.status(f"Put back {restored} queue item(s)", ms=0)


def _refresh(host, section) -> None:
    section.refresh()
    host.load_history()          # watch history moved between copies
