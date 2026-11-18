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
- **Nothing to replace them**: greyed, with the reason, and left in the queue.

A row with several copies has a drop-down. Nothing changes until Replace,
which keeps the window open: the swapped rows drop out and the doubtful ones
move up to be checked next (owner). Each Replace gets its own Undo, and what is
left can be revisited from the same menu any time.
"""

from __future__ import annotations

from loguru import logger
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel,
    QRadioButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from streamselect.core.queue_replacement import (
    SCOPE_ALL, SCOPE_EXPIRED, Copy, Stranded, find_stranded, replace, undo,
)
from streamselect.gui import icon_utils as _icon_utils
from streamselect.gui import theme as _theme
from streamselect.gui.dialog_chrome import dialog_buttons

COL_OLD, COL_ARROW, COL_NEW, COL_NOTE = 0, 1, 2, 3
GROUP_SURE, GROUP_CHECK, GROUP_NONE = "Ready to replace", "Check these first", "Nothing to replace them"
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
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["In your queue", "", "Replace with", "Note"])
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(COL_OLD, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_ARROW, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COL_NEW, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_NOTE, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setColumnWidth(COL_ARROW, 28)
        self.tree.itemChanged.connect(lambda *_: self._update_count())
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
        font = group.font(COL_OLD)
        font.setBold(True)
        group.setFont(COL_OLD, font)
        group.setFirstColumnSpanned(True)
        flags = Qt.ItemFlag.ItemIsEnabled
        if checkable:
            flags |= Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate
            group.setToolTip(COL_OLD, f"Tick or clear every item under {title}")
        group.setFlags(flags)
        self.tree.addTopLevelItem(group)
        self.groups[title] = group
        return group

    def _fill(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        self._rows, self.groups = [], {}
        shown = self.shown()
        sure = [s for s in shown if s.best is not None and not s.doubts]
        check = [s for s in shown if s.best is not None and s.doubts]
        none = [s for s in shown if s.best is None]
        arrow = _icon_utils.role_icon("replace_with", _theme.COLOR_MUTED)
        muted = QBrush(QColor(_theme.COLOR_MUTED))
        for title, rows, ticked in ((GROUP_SURE, sure, True), (GROUP_CHECK, check, False),
                                    (GROUP_NONE, none, None)):
            group = self._group(title, rows, checkable=ticked is not None)
            for s in rows:
                old = f"{describe(s.old)} · {_STATE_WORDS.get(s.state, s.state)}"
                item = QTreeWidgetItem([old, "", "", ""])
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
                    else:
                        item.setText(COL_NEW, describe_new(s.best))
                        item.setToolTip(COL_NEW, item.text(COL_NEW))
                self._rows.append((s, item, combo))
            if group is not None:
                group.setExpanded(True)
        self.tree.blockSignals(False)
        self._update_count()

    def _replace(self) -> None:
        picked = self.choices()
        if picked and self._on_replace is not None:
            self._on_replace(picked)

    def reload(self, stranded: list[Stranded]) -> None:
        """Show a fresh scan, after a Replace or an Undo, keeping the scope."""
        self._all = stranded
        self._fill()

    def choices(self) -> list[tuple[int, str]]:
        """``(queue_id, channel_id)`` for every ticked row, with its picked copy."""
        out = []
        for s, item, combo in self._rows:
            if s.best is None or item.checkState(COL_OLD) != Qt.CheckState.Checked:
                continue
            out.append((s.queue_id, combo.currentData() if combo is not None else s.best.channel_id))
        return out

    def _update_count(self) -> None:
        shown = [s for s, _i, _c in self._rows]
        ticked = len(self.choices())
        if not shown:
            self.summary.setText("Nothing to replace: every queued item in this group is on an "
                                 "active source.")
        else:
            self.summary.setText(f"{len(shown)} unavailable · {ticked} ticked to replace. "
                                 "Unticked items stay as they are, and you can come back to "
                                 "them from the same menu.")
        if self._ok is not None:
            self._ok.setText(f"Replace {ticked}" if ticked else "Replace")
            self._ok.setEnabled(bool(ticked))


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

        dialog._on_replace = lambda picked: apply_replacements(host, section, picked, rescan)
        dialog.exec()

    scan(show)


def apply_replacements(host, section, choices: list[tuple[int, str]], after=None) -> None:
    """Swap the chosen items, refresh, and offer Undo. *after* runs after
    both the swap and an Undo (the open window re-reads)."""
    if not choices:
        return
    try:
        with host.db.session_scope() as session:
            done, skipped, snapshot = replace(session, choices)
    except Exception as e:  # noqa: BLE001 — a failed swap must not crash the window
        logger.error(f"Replacing queue items failed: {e}")
        host.status(f"Couldn't replace queue items: {e}", ms=0, level="error")
        return
    _refresh(host, section)
    if after is not None:
        after()
    note = f" {skipped} already in the queue were left as they were." if skipped else ""
    logger.info("Watch Queue: replaced {} unavailable item(s), {} skipped", done, skipped)
    host.status(f"Replaced {done} queue item(s)", ms=0)
    host.notification_manager.show(
        title="Watch Queue updated",
        message=f"Replaced {done} item(s) with copies on active sources.{note}",
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
