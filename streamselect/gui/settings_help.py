"""Settings' right-hand column: every setting on the page explained, and the row you are on.

The column used to hold one paragraph per section. It now keeps that paragraph and
lists every setting under it, grouped like the page (owner, 2026-11-22, Q3-Q10 of the
Settings redesign). Clicking a setting's label, or moving into its value, jumps the
column to that setting and tints its row; clicking a name in the column scrolls the page
to its row. Settings can also open at one row (:meth:`SettingsHelp.select_setting`), and
the find box keeps only the sections and rows whose name or explanation matches.

**The explanation IS the control's tooltip.** Nothing here holds help text of its own,
so the hover text and the column cannot disagree, and a setting is explained in exactly
one place. A setting without a tooltip has no explanation, and
``tests/test_settings_help.py`` fails on it.

Settings are FOUND, never listed: a page is walked for its controls and each one's name
comes from where it sits (its form label, its own checkbox text, the label before it).
A hand-kept list of rows would miss the next setting someone adds.
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field

from PyQt6.QtCore import QEvent, QObject, QRect, Qt, QTimer, QUrl
from PyQt6.QtWidgets import (
    QAbstractButton, QAbstractSpinBox, QApplication, QCheckBox, QComboBox, QFormLayout, QFrame,
    QGroupBox, QLabel, QLayout, QLineEdit, QListWidget, QPushButton, QRadioButton, QScrollArea,
    QWidget,
)

from streamselect.gui import theme as _theme

#: The kinds of widget that hold a setting's value. Buttons are actions, not settings.
SETTING_WIDGETS = (QCheckBox, QRadioButton, QComboBox, QAbstractSpinBox, QLineEdit, QListWidget)

#: How long a row opened from a link stays strongly tinted before it settles.
LINK_TINT_MS = 2000


@dataclass
class SettingEntry:
    """One setting on a page: its name, explanation, and the widgets that make it up."""

    title: str
    group: str
    label: QWidget                      # the widget showing the name (may be the control)
    control: QWidget
    extras: list[QWidget] = field(default_factory=list)   # e.g. a checkbox's "Wait" box

    @property
    def explanation(self) -> str:
        parts = [self.control.toolTip() or self.label.toolTip()]
        parts += [w.toolTip() for w in self.extras if w.toolTip() and w.toolTip() not in parts]
        return "\n\n".join(p for p in parts if p)

    def widgets(self) -> list[QWidget]:
        return [self.label, self.control, *self.extras]

    def owns(self, widget: QWidget) -> bool:
        return any(w is widget or w.isAncestorOf(widget) for w in (self.control, *self.extras))


def _layout_holds(layout: QLayout, widget: QWidget) -> bool:
    for i in range(layout.count()):
        item = layout.itemAt(i)
        w = item.widget()
        if w is not None and (w is widget or w.isAncestorOf(widget)):
            return True
        if item.layout() is not None and _layout_holds(item.layout(), widget):
            return True
    return False


def _form_label(forms: list[QFormLayout], widget: QWidget) -> QLabel | None:
    """The non-empty form label of the row whose field holds *widget*."""
    for form in forms:
        for row in range(form.rowCount()):
            fld = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if fld is None:
                continue
            held = (fld.widget() is not None and (fld.widget() is widget or fld.widget().isAncestorOf(widget))) \
                or (fld.layout() is not None and _layout_holds(fld.layout(), widget))
            if held:
                lab = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
                w = lab.widget() if lab is not None else None
                return w if isinstance(w, QLabel) and w.text().strip() else None
    return None


def _containing_layout(layout: QLayout | None, widget: QWidget) -> QLayout | None:
    if layout is None:
        return None
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item.widget() is widget:
            return layout
        if item.layout() is not None:
            found = _containing_layout(item.layout(), widget)
            if found is not None:
                return found
    return None


def _siblings_before(widget: QWidget) -> list[QWidget]:
    """The widgets before *widget* in the layout that directly holds it, nearest first."""
    parent = widget.parentWidget()
    lay = _containing_layout(parent.layout() if parent is not None else None, widget)
    if lay is None:
        return []
    before = []
    for i in range(lay.count()):
        w = lay.itemAt(i).widget()
        if w is widget:
            break
        if w is not None:
            before.append(w)
    return before[::-1]


def _group_title(widget: QWidget) -> str:
    p = widget.parentWidget()
    while p is not None and not isinstance(p, QGroupBox):
        p = p.parentWidget()
    return p.title() if p is not None else ""


def _clean(text: str) -> str:
    return text.replace("&", "").strip().rstrip(":").strip()


def page_entries(page: QWidget) -> list[SettingEntry]:
    """Every setting on *page*, in page order.

    A control is named by, in order: its accessible name; its form row's label; its own
    text (a checkbox); a checkbox before it on the same line (then it JOINS that
    checkbox's entry: "Pre-buffer before playing — Wait"); the label before it on the
    same line; its group box's title.
    """
    forms = page.findChildren(QFormLayout)
    entries: list[SettingEntry] = []
    by_checkbox: dict[int, SettingEntry] = {}
    for w in page.findChildren(QWidget):
        if not isinstance(w, SETTING_WIDGETS) or isinstance(w, QPushButton):
            continue
        parent = w.parentWidget()
        if isinstance(parent, (QAbstractSpinBox, QComboBox)):
            continue                       # a spin box's or combo's own line edit
        group = _group_title(w)
        if w.accessibleName():
            entries.append(SettingEntry(w.accessibleName(), group, w, w))
            continue
        label = _form_label(forms, w)
        if label is not None and not isinstance(w, QAbstractButton):
            entries.append(SettingEntry(_clean(label.text()), group, label, w))
            continue
        if isinstance(w, (QCheckBox, QRadioButton)):
            entry = SettingEntry(_clean(w.text()), group, w, w)
            by_checkbox[id(w)] = entry
            entries.append(entry)
            continue
        before = _siblings_before(w)
        box = next((b for b in before if isinstance(b, QCheckBox)), None)
        if box is not None and id(box) in by_checkbox:
            by_checkbox[id(box)].extras.append(w)
            continue
        text = next((b for b in before if isinstance(b, QLabel) and b.text().strip()), None)
        if text is not None:
            entries.append(SettingEntry(_clean(text.text()), group, text, w))
        elif label is not None:
            entries.append(SettingEntry(_clean(label.text()), group, label, w))
        elif group:
            entries.append(SettingEntry(group, group, w, w))
    return entries


def _explanation_html(text: str) -> str:
    """A tooltip as a paragraph: its hard line breaks were for the tooltip's width."""
    paras = [" ".join(line.strip() for line in p.splitlines()) for p in text.split("\n\n")]
    out = "<br><br>".join(html.escape(p) for p in paras if p)
    return out.replace(" • ", "<br>• ")


class _RowTint(QFrame):
    """A soft tint behind one setting's row, so you can see which row the column means."""

    def __init__(self, page: QWidget, entry: SettingEntry, strong: bool):
        super().__init__(page)
        self.entry = entry
        self.setObjectName("settingRowTint")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.set_strong(strong)
        self.place()
        self.lower()
        self.show()

    def set_strong(self, strong: bool) -> None:
        fill = "OVERLAY_ACCENT_35" if strong else "OVERLAY_SELECTION"
        _theme.style_fn(self, lambda: f"QFrame#settingRowTint {{ background: {getattr(_theme, fill)};"
                        f" border-left: 3px solid {_theme.COLOR_ACCENT}; border-radius: 3px; }}")

    def place(self) -> None:
        page = self.parentWidget()
        rect = QRect()
        for w in self.entry.widgets():
            if w.isVisibleTo(page):
                rect = rect.united(QRect(w.mapTo(page, w.rect().topLeft()), w.size()))
        self.setGeometry(rect.adjusted(-8, -3, 8, 3))


class SettingsHelp(QObject):
    """Fills a :class:`ThreePanelSectionNav`'s help panel and keeps it on the row you are on."""

    def __init__(self, nav, section_help: dict[str, str], parent: QObject | None = None):
        super().__init__(parent)
        self._nav = nav
        self._section_help = section_help
        self._entries: dict[int, list[SettingEntry]] = {}
        self._active: dict[int, int] = {}              # section index -> entry index
        self._tints: dict[int, list[_RowTint]] = {}
        self._query = ""
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.timeout.connect(self._settle_tints)
        nav.pageShown.connect(self._render)
        nav.findTextChanged.connect(self.find)
        nav.help_panel.anchorClicked.connect(self._on_anchor)
        QApplication.instance().focusChanged.connect(self._on_focus)

    # ── what is on a page ─────────────────────────────────────────────────
    def entries(self, index: int) -> list[SettingEntry]:
        """The settings of section *index* (found once, on first ask)."""
        if index not in self._entries:
            page = self._nav.page(index)
            found = page_entries(page)
            for entry in found:
                if entry.label is not entry.control:
                    entry.label.installEventFilter(self)
            page.installEventFilter(self)
            self._entries[index] = found
        return self._entries[index]

    def _matches(self, entry: SettingEntry) -> bool:
        q = self._query
        return bool(q) and (q in entry.title.lower() or q in entry.explanation.lower())

    # ── the column ────────────────────────────────────────────────────────
    def _render(self, index: int) -> None:
        if not 0 <= index < self._nav.count():
            return
        page = self._nav.page(index)
        entries = self.entries(index)
        active = self._active.get(index)
        if self._query:
            for entry in entries:
                if self._matches(entry) and not entry.control.isVisibleTo(page):
                    self._reveal(page, entry)
        parts = [f"<p>{html.escape(self._section_help.get(self._nav.section_id(index), ''))}</p>"]
        group = None
        for i, entry in enumerate(entries):
            if not entry.control.isVisibleTo(page):
                continue
            if entry.group and entry.group != group:
                parts.append(f"<p style='color:{_theme.COLOR_MUTED}; font-size:{_theme.FONT_SM};"
                             f" margin-top:12px'>{html.escape(entry.group.upper())}</p>")
            group = entry.group
            lit = i == active or self._matches(entry)
            bar = _theme.COLOR_ACCENT if lit else "transparent"
            fill = f"background-color:{_theme.OVERLAY_SELECTION};" if lit else ""
            parts.append(
                f"<a name='s{i}'></a><table width='100%' cellspacing='0' cellpadding='0'"
                f" style='margin-top:6px'><tr><td width='3' style='background-color:{bar}'></td>"
                f"<td style='{fill} padding:4px 6px'><a href='setting:{i}' style='color:"
                f"{_theme.COLOR_TEXT_HI}; text-decoration:none'><b>{html.escape(entry.title)}</b></a>"
                f"{'<br>' if entry.explanation else ''}{_explanation_html(entry.explanation)}"
                "</td></tr></table>")
        bar = self._nav.help_panel.verticalScrollBar()
        keep = bar.value()
        self._nav.help_panel.setHtml("".join(parts))
        bar.setValue(keep)
        self._tint(index, [e for i, e in enumerate(entries) if i == active or self._matches(e)])

    def show_entry(self, index: int, entry_index: int, *, strong: bool = False) -> None:
        """Make one setting the column's subject: its text at the top, its row tinted."""
        self._active[index] = entry_index
        self._render(index)
        self._nav.help_panel.scrollToAnchor(f"s{entry_index}")
        if strong:
            for tint in self._tints.get(index, []):
                if tint.entry is self.entries(index)[entry_index]:
                    tint.set_strong(True)
            self._settle.start(LINK_TINT_MS)

    def _settle_tints(self) -> None:
        for tints in self._tints.values():
            for tint in tints:
                tint.set_strong(False)

    def _tint(self, index: int, entries: list[SettingEntry]) -> None:
        for tint in self._tints.pop(index, []):
            tint.hide()
            tint.deleteLater()
        page = self._nav.page(index)
        self._tints[index] = [_RowTint(page, e, False) for e in entries if e.control.isVisibleTo(page)]

    # ── ways in ───────────────────────────────────────────────────────────
    def eventFilter(self, obj, event) -> bool:
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress:
            index = self._nav.current_row()
            for i, entry in enumerate(self.entries(index) if index >= 0 else []):
                if entry.label is obj:
                    self.show_entry(index, i)
                    break
        elif kind in (QEvent.Type.Resize, QEvent.Type.LayoutRequest):
            for tints in self._tints.values():
                for tint in tints:
                    if tint.parentWidget() is obj:
                        tint.place()
        return False

    def _on_focus(self, _old, new) -> None:
        index = self._nav.current_row()
        if new is None or index < 0 or not self._nav.page(index).isAncestorOf(new):
            return
        for i, entry in enumerate(self.entries(index)):
            if entry.owns(new) and self._active.get(index) != i:
                self.show_entry(index, i)
                return

    def _on_anchor(self, url: QUrl) -> None:
        text = url.toString()
        index = self._nav.current_row()
        if not text.startswith("setting:") or index < 0:
            return
        i = int(text.split(":", 1)[1])
        self._scroll_to(index, self.entries(index)[i])
        self.show_entry(index, i)

    def select_setting(self, index: int, name: str) -> bool:
        """Open section *index* at the setting called *name* (object name, or a
        case-insensitive part of its title). Returns False when there is none."""
        if not 0 <= index < self._nav.count():
            return False
        want = name.strip().lower()
        entries = self.entries(index)
        i = next((i for i, e in enumerate(entries) if e.control.objectName().lower() == want), None)
        if i is None:
            i = next((i for i, e in enumerate(entries) if want and want in e.title.lower()), None)
        if i is None:
            return False
        self._nav.set_current_row(index)
        page = self._nav.page(index)
        self._reveal(page, entries[i])
        self._scroll_to(index, entries[i])
        self.show_entry(index, i, strong=True)
        return True

    def find(self, text: str) -> None:
        """Keep only the sections, rows and explanations that mention *text*."""
        self._query = text.strip().lower()
        if not self._query:
            self._nav.set_match_counts(None)
        else:
            counts = {i: sum(1 for e in self.entries(i) if self._matches(e))
                      for i in range(self._nav.count())}
            counts = {i: n for i, n in counts.items() if n}
            self._nav.set_match_counts(counts)
            self._active.clear()               # the column follows the matches now
            if counts and self._nav.current_row() not in counts:
                self._nav.set_current_row(min(counts))
            else:
                self._render(self._nav.current_row())
            self._show_first_match()
            return
        self._render(self._nav.current_row())

    def _show_first_match(self) -> None:
        index = self._nav.current_row()
        page = self._nav.page(index) if index >= 0 else None
        for i, entry in enumerate(self.entries(index) if page is not None else []):
            if self._matches(entry) and entry.control.isVisibleTo(page):
                self._scroll_to(index, entry)
                self._nav.help_panel.scrollToAnchor(f"s{i}")
                return

    def _reveal(self, page: QWidget, entry: SettingEntry) -> None:
        """A row inside a closed box: ask the page to open it (only some pages can)."""
        reveal = getattr(page, "reveal_setting", None)
        if reveal is not None:
            reveal(entry.control)

    def _scroll_to(self, index: int, entry: SettingEntry) -> None:
        area = self._nav.stack.widget(index)
        if isinstance(area, QScrollArea):
            QApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest.value)
            area.ensureWidgetVisible(entry.control, 50, 80)
