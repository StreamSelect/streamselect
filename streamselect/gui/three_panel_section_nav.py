"""Left-nav / center-stack / right-help three-panel section switcher.

A small, dialog-agnostic composite widget: a find box over a ``QListWidget`` of
section labels on the left (optionally under group headings), a ``QStackedWidget``
of section pages in the center, and a help ``QTextBrowser`` on the right. Built for
:class:`~streamselect.gui.settings_dialog.SettingsDialog` and split out so that
file stays small; it knows nothing about Config or any Settings content, so a
future multi-section surface can reuse it. What the help panel SAYS is the host's
business: it fills ``help_panel`` when ``pageShown`` fires.

Sections are addressed by their INDEX (the order they were added, which is also
the stack index), never by list row: a heading takes a list row but is not a
section, so the two numberings differ as soon as there is one heading.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QListWidget, QListWidgetItem, QScrollArea, QStackedWidget, QTextBrowser,
    QVBoxLayout, QWidget,
)

from streamselect.gui import theme as _theme
from streamselect.gui.scoped_filter_box import ScopedFilterBox
from streamselect.gui.token_color import to_qcolor

#: Width of the help column: wide enough for one setting's explanation to read as a
#: paragraph rather than a ribbon (owner, 2026-11-22: Q6 of the Settings redesign).
HELP_WIDTH = 280

_SECTION_ROLE = Qt.ItemDataRole.UserRole          # section index (int) on a section row
_LABEL_ROLE = Qt.ItemDataRole.UserRole + 1        # the bare label, without a match count


class ThreePanelSectionNav(QWidget):
    """Find box + section list (with optional headings), stacked pages, help panel.

    Call :meth:`add_heading` / :meth:`add_section` in display order, then
    :meth:`set_current_row` to select the first section shown.

    Signals:
        sectionChanged(int): a USER-driven change of section (its index).
        pageShown(int): a section's page became current, by any route — the
            host refreshes ``help_panel`` from here.
        findTextChanged(str): the find box's text, debounced.
    """

    sectionChanged = pyqtSignal(int)
    pageShown = pyqtSignal(int)
    findTextChanged = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._section_ids: list[str] = []
        self._section_rows: list[int] = []        # section index -> list row

        layout = QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self.find_box = ScopedFilterBox("Find a setting…", debounce_ms=200)
        self.find_box.setToolTip("Find a setting by its name or what it does.")
        self.find_box.filterChanged.connect(self.findTextChanged)

        self.section_list = QListWidget()
        self.section_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.section_list.setToolTip("Choose a settings section.")
        _theme.style_fn(self.section_list, lambda: "QListWidget { border: none; background: transparent; "
            f"font-size: {_theme.FONT_XL}; outline: none; }}"
            f"QListWidget::item {{ padding: 5px 12px; color: {_theme.COLOR_TEXT}; }}"
            "QListWidget::item:hover { background: "
            f"{_theme.COLOR_LINE_DARK}; color: {_theme.COLOR_TEXT}; }}")
        # Shared "coloured-text item view" selection chokepoint (soft tint +
        # left accent bar) — appends onto the base stylesheet above.
        _theme.apply_list_selection(self.section_list)

        self.nav_column = QFrame()
        _theme.style_fn(self.nav_column, lambda: "QFrame#navColumn { border: none; border-right: 1px solid "
                        f"{_theme.COLOR_LINE}; }}")
        self.nav_column.setObjectName("navColumn")
        col = QVBoxLayout(self.nav_column)
        col.setContentsMargins(6, 0, 0, 0)
        col.setSpacing(6)
        col.addWidget(self.find_box)
        col.addWidget(self.section_list, 1)
        self._fit_nav_width()

        self.stack = QStackedWidget()

        self.help_panel = QTextBrowser()
        self.help_panel.setFixedWidth(HELP_WIDTH)
        self.help_panel.setOpenLinks(False)
        self.help_panel.setReadOnly(True)
        self.help_panel.setToolTip("What the settings on this page do.")
        _theme.style_fn(self.help_panel, lambda: "QTextBrowser { border: none; border-left: 1px solid "
            f"{_theme.COLOR_LINE}; background: transparent; color: {_theme.COLOR_TEXT};"
            f" font-size: {_theme.FONT_MD}; padding: 10px; }}")

        layout.addWidget(self.nav_column)
        layout.addWidget(self.stack, 1)
        layout.addWidget(self.help_panel)

        self.section_list.currentRowChanged.connect(self._on_row_changed)

    def add_heading(self, text: str) -> None:
        """Append a group heading: a list row that is not a section and cannot be
        selected (the arrow keys step over it)."""
        item = QListWidgetItem(text.upper())
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        font = QFont(self.section_list.font())
        font.setBold(True)
        font.setPixelSize(11)
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 108)
        item.setFont(font)
        item.setForeground(to_qcolor(_theme.COLOR_MUTED))
        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        item.setSizeHint(QSize(10, 36 if self.section_list.count() else 24))
        self.section_list.addItem(item)

    def add_section(self, section_id: str, label: str, page: QWidget) -> None:
        """Append a section row labeled *label* and its center *page*.

        The page scrolls inside its own frameless area. Placed bare in the stack,
        a page wider than the centre column was squeezed below its minimum (labels
        drawn under their fields, values cut off), and the tallest page's height
        became the whole dialog's minimum (824 px; owner, 2026-11-22).
        """
        item = QListWidgetItem(label)
        item.setData(_SECTION_ROLE, len(self._section_ids))
        item.setData(_LABEL_ROLE, label)
        item.setToolTip(f"Show {label} settings")
        self.section_list.addItem(item)
        self._section_rows.append(self.section_list.count() - 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        self.stack.addWidget(scroll)
        self._section_ids.append(section_id)
        self._fit_nav_width()

    def _fit_nav_width(self) -> None:
        """Size the list to its widest row, plus room for a match count."""
        self.section_list.ensurePolished()
        widest = self.section_list.sizeHintForColumn(0) + 2 * self.section_list.frameWidth() + 4
        width = max(160, widest + self.section_list.fontMetrics().horizontalAdvance("  00"))
        self.section_list.setFixedWidth(width)
        self.find_box.setFixedWidth(width - 6)

    def count(self) -> int:
        """Number of sections (headings not counted)."""
        return len(self._section_ids)

    def section_id(self, index: int) -> str:
        return self._section_ids[index]

    def index_of(self, section_id: str) -> int:
        """The index of *section_id*, or -1."""
        return self._section_ids.index(section_id) if section_id in self._section_ids else -1

    def page(self, index: int) -> QWidget:
        """The page widget of section *index* (inside its scroll area)."""
        return self.stack.widget(index).widget()

    def label(self, index: int) -> str:
        return self.section_list.item(self._section_rows[index]).data(_LABEL_ROLE)

    def current_row(self) -> int:
        """The current SECTION index (not list row), or -1."""
        item = self.section_list.currentItem()
        return item.data(_SECTION_ROLE) if item is not None and item.data(_SECTION_ROLE) is not None else -1

    def set_current_row(self, index: int, *, block_signal: bool = False) -> None:
        """Select section *index*.

        Pass ``block_signal=True`` during a restore-from-config so this does
        not fire ``sectionChanged`` (the project rules: signal blocking during UI
        state restoration) — the page/help sync still happens either way.
        """
        if not 0 <= index < self.count():
            return
        row = self._section_rows[index]
        if block_signal:
            self.section_list.blockSignals(True)
            self.section_list.setCurrentRow(row)
            self.section_list.blockSignals(False)
            self._sync_page(index)
        else:
            self.section_list.setCurrentRow(row)

    def select_by_label(self, label_substring: str) -> bool:
        """Select the first section whose label contains *label_substring*
        (case-insensitive). Returns True if a match was found and selected."""
        want = label_substring.strip().lower()
        for index in range(self.count()):
            if want in self.label(index).lower():
                self.set_current_row(index)
                return True
        return False

    def set_match_counts(self, counts: dict[int, int] | None) -> None:
        """Show only the sections in *counts*, each with its count; ``None`` shows all.

        A heading with no section left under it hides too.
        """
        lst = self.section_list
        heading = None
        heading_has_rows = False
        for row in range(lst.count()):
            item = lst.item(row)
            index = item.data(_SECTION_ROLE)
            if index is None:
                if heading is not None:
                    heading.setHidden(not heading_has_rows)
                heading, heading_has_rows = item, False
                continue
            label = item.data(_LABEL_ROLE)
            shown = counts is None or counts.get(index, 0) > 0
            item.setHidden(not shown)
            item.setText(label if counts is None or not shown else f"{label}   {counts[index]}")
            heading_has_rows = heading_has_rows or shown
        if heading is not None:
            heading.setHidden(not heading_has_rows)

    def _on_row_changed(self, row: int) -> None:
        item = self.section_list.item(row)
        index = item.data(_SECTION_ROLE) if item is not None else None
        if index is None:
            return
        self._sync_page(index)
        self.sectionChanged.emit(index)

    def _sync_page(self, index: int) -> None:
        if 0 <= index < self.stack.count():
            self.stack.setCurrentIndex(index)
            self.pageShown.emit(index)
