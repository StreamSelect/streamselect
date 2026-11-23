"""Settings, reorganized (owner, 2026-11-22: Q1-Q10 and Q12 of the Settings redesign).

Sections sit under task headings; the right column explains every setting on the page;
clicking a label, or moving into a value, jumps the column to that setting and tints
its row; Settings can open at one setting; value boxes fit their values; a find box
keeps only the matching sections and rows. These assert what is painted: which block
of the column is at its top, where the tint sits, how wide a box is drawn.
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint, QRect, Qt, QUrl
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QAbstractSpinBox, QApplication, QCheckBox, QComboBox, QLabel

#: Saved and shown, but read by nothing — reported to the owner (2026-11-22), not explained,
#: since an explanation would describe something that does not happen.
UNUSED_SETTINGS = {"Network timeout", "Reconnect attempts", "Cache TTL (fresh content)"}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settle(qapp, n=6):
    for _ in range(n):
        qapp.processEvents()


@pytest.fixture
def dialog(qapp):
    from streamselect.core.config import Config
    from streamselect.gui.settings_dialog import SettingsDialog

    dlg = SettingsDialog(Config())
    dlg.resize(dlg.minimumWidth(), 600)
    dlg.show()
    _settle(qapp)
    yield dlg
    from tests.conftest import destroy_widget
    destroy_widget(dlg)


def _index(dialog, label: str) -> int:
    nav = dialog._nav
    return next(i for i in range(nav.count()) if nav.label(i) == label)


def _top_of_column(dialog) -> str:
    """The text of the block drawn at the top of the help column."""
    panel = dialog._nav.help_panel
    return panel.cursorForPosition(QPoint(30, 12)).block().text().split("\u2028")[0]


def _rect_in(widget, ancestor) -> QRect:
    return QRect(widget.mapTo(ancestor, QPoint(0, 0)), widget.size())


def _tints(dialog, index):
    return [t for t in dialog._help._tints.get(index, []) if t.isVisible()]


# ── Q1: grouped list ──────────────────────────────────────────────────────

def test_sections_sit_under_headings_that_cannot_be_selected(dialog, qapp):
    from streamselect.gui.settings_dialog import SECTION_GROUPS

    lst = dialog._nav.section_list
    headings = [lst.item(r) for r in range(lst.count())
                if lst.item(r).flags() == Qt.ItemFlag.NoItemFlags]
    assert [h.text() for h in headings] == [g.upper() for g, _ in SECTION_GROUPS]
    # Each heading is drawn above the sections of its group.
    first_of_group2 = SECTION_GROUPS[1][1][0][1]
    row2 = next(r for r in range(lst.count()) if lst.item(r).text() == first_of_group2)
    assert lst.visualItemRect(lst.item(row2 - 1)).bottom() <= lst.visualItemRect(lst.item(row2)).top()
    assert lst.item(row2 - 1) is headings[1]
    # The arrow keys step over a heading.
    last_of_group1 = SECTION_GROUPS[0][1][-1][1]
    dialog._nav.set_current_row(_index(dialog, last_of_group1))
    lst.setFocus()
    QTest.keyClick(lst, Qt.Key.Key_Down)
    assert dialog._nav.label(dialog._nav.current_row()) == first_of_group2


# ── Q3/Q4: every setting explained ───────────────────────────────────────

def test_every_setting_has_an_explanation(dialog):
    missing = []
    for i in range(dialog._nav.count()):
        for entry in dialog._help.entries(i):
            if not entry.explanation and entry.title not in UNUSED_SETTINGS:
                missing.append(f"{dialog._nav.label(i)} ▸ {entry.title}")
    assert not missing, "settings with no tooltip (= no explanation): " + ", ".join(missing)
    titles = {e.title for i in range(dialog._nav.count()) for e in dialog._help.entries(i)}
    assert UNUSED_SETTINGS <= titles, "an unused setting was removed or wired: update UNUSED_SETTINGS"


def test_the_column_lists_every_setting_on_the_page(dialog, qapp):
    dialog._nav.set_current_row(_index(dialog, "Playback"))
    _settle(qapp)
    text = dialog._nav.help_panel.toPlainText()
    entries = dialog._help.entries(_index(dialog, "Playback"))
    assert len(entries) >= 15
    for entry in entries:
        assert entry.title in text
    assert "PLAYER" in text and "NETWORK" in text            # grouped like the page


# ── Q5: label click / focus ──────────────────────────────────────────────

def test_clicking_a_label_puts_its_explanation_on_top_and_tints_its_row(dialog, qapp):
    index = _index(dialog, "Playback")
    dialog._nav.set_current_row(index)
    _settle(qapp)
    page = dialog._nav.page(index)
    label = next(w for w in page.findChildren(QLabel) if w.text() == "Buffering:")
    QTest.mouseClick(label, Qt.MouseButton.LeftButton)
    _settle(qapp)
    assert _top_of_column(dialog) == "Buffering"
    (tint,) = _tints(dialog, index)
    assert tint.geometry().contains(_rect_in(label, page))
    assert tint.geometry().contains(_rect_in(dialog._buffer_combo, page))


def test_moving_into_a_value_puts_its_explanation_on_top(dialog, qapp):
    index = _index(dialog, "Playback")
    dialog._nav.set_current_row(index)
    _settle(qapp)
    dialog._video_decoder_combo.setFocus()
    _settle(qapp)
    assert _top_of_column(dialog) == "Video decoder"


def test_clicking_a_name_in_the_column_scrolls_the_page_to_it(dialog, qapp):
    index = _index(dialog, "Playback")
    dialog._nav.set_current_row(index)
    _settle(qapp)
    entries = dialog._help.entries(index)
    last = len(entries) - 1
    dialog._nav.help_panel.anchorClicked.emit(QUrl(f"setting:{last}"))
    _settle(qapp)
    area = dialog._nav.stack.widget(index)
    shown = _rect_in(entries[last].control, area.viewport())
    assert area.viewport().rect().contains(shown)


# ── Q7: open at one setting ──────────────────────────────────────────────

def _assert_opened_at_still_here(dialog, qapp):
    index = _index(dialog, "Sidebar")
    assert dialog._nav.current_row() == index
    check = dialog._prompt_after_autoplay_check
    area = dialog._nav.stack.widget(index)
    assert area.viewport().rect().contains(_rect_in(check, area.viewport()))
    # In view in the help column (the History group closes the Sidebar page, so the
    # column cannot scroll its entry all the way to the top).
    panel = dialog._nav.help_panel
    found = panel.document().find("Ask how many episodes you watched")
    assert not found.isNull()
    assert panel.viewport().rect().contains(panel.cursorRect(found).center())
    (tint,) = _tints(dialog, index)
    assert tint.geometry().contains(_rect_in(check, dialog._nav.page(index)))


def test_settings_opens_at_the_setting_the_watched_prompt_links_to(dialog, qapp):
    from streamselect.gui.queue_end_prompt import PROMPT_SETTING_LINK

    tab, _, setting = PROMPT_SETTING_LINK.removeprefix("settings:").partition("/")
    dialog._nav.set_current_row(_index(dialog, "Sports"))
    assert dialog.select_setting(tab, setting) is True
    _settle(qapp)
    _assert_opened_at_still_here(dialog, qapp)


def test_a_link_given_before_the_dialog_shows_lands_once_it_does(qapp):
    from streamselect.core.config import Config
    from streamselect.gui.settings_dialog import SettingsDialog
    from tests.conftest import destroy_widget

    dlg = SettingsDialog(Config())
    try:
        assert dlg.select_setting("Sidebar", "Ask how many episodes") is True
        dlg.resize(dlg.minimumWidth(), 360)        # short, so the row needs scrolling into view
        dlg.show()
        _settle(qapp, 10)
        _assert_opened_at_still_here(dlg, qapp)
    finally:
        destroy_widget(dlg)


def test_the_watched_prompt_links_to_its_setting(qapp, monkeypatch):
    from unittest.mock import MagicMock

    from PyQt6.QtWidgets import QDialog

    from streamselect.gui.queue_end_prompt import PROMPT_SETTING_LINK, _QueueEndPromptMixin

    host = _QueueEndPromptMixin.__new__(_QueueEndPromptMixin)
    host.config = MagicMock(prompt_after_autoplay=True)
    host.executor = MagicMock()
    host.navigate_to = MagicMock()
    QDialog_init = QDialog.__init__
    monkeypatch.setattr(QDialog, "__init__", lambda self, _parent=None: QDialog_init(self))

    def _click_link(dlg):
        link = next(w for w in dlg.findChildren(QLabel) if "<a " in w.text())
        assert PROMPT_SETTING_LINK in link.text()
        link.linkActivated.emit(PROMPT_SETTING_LINK)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", _click_link)
    host._on_queue_end_detected(["ep2"])
    host.navigate_to.assert_called_once_with(PROMPT_SETTING_LINK)


# ── Q8: value boxes fit their values ─────────────────────────────────────

def test_number_boxes_fit_their_values_and_text_fields_stretch(dialog, qapp):
    index = _index(dialog, "Signal checking")
    dialog._nav.set_current_row(index)
    _settle(qapp)
    column = dialog._nav.stack.widget(index).viewport().width()
    spins = [s for s in dialog._nav.page(index).findChildren(QAbstractSpinBox) if s.isVisible()]
    assert len(spins) >= 4
    for spin in spins:
        assert spin.width() >= spin.minimumSizeHint().width()
        assert spin.width() < column / 3, f"{spin.text()!r} stretched to {spin.width()} px"
    dialog._nav.set_current_row(_index(dialog, "Playback"))
    _settle(qapp)
    assert dialog._user_agent_view.width() > 2 * dialog._video_decoder_combo.width()


# ── Q9/Q10: find ─────────────────────────────────────────────────────────

def test_find_keeps_only_matching_sections_with_their_counts(dialog, qapp):
    from streamselect.gui.settings_dialog import SECTION_GROUPS

    nav = dialog._nav
    dialog._help.find("buffer")
    _settle(qapp)
    lst = nav.section_list
    shown = [lst.item(r).text() for r in range(lst.count()) if not lst.item(r).isHidden()]
    assert shown[0] == SECTION_GROUPS[0][0].upper()
    assert any(t.startswith("Playback") and t.split()[-1].isdigit() for t in shown)
    assert "Sidebar" not in shown and "FINDING THINGS" not in shown and "ALERTS" not in shown
    current = lst.item(nav._section_rows[nav.current_row()]).text()
    assert current in shown, "the page shown is one with a match"
    assert _tints(dialog, nav.current_row()), "matching rows are tinted"
    dialog._help.find("")
    _settle(qapp)
    assert all(not lst.item(r).isHidden() for r in range(lst.count()))
    assert [lst.item(r).text() for r in range(lst.count())
            if lst.item(r).flags() != Qt.ItemFlag.NoItemFlags] == [nav.label(i) for i in range(nav.count())]


def test_find_opens_the_closed_box_a_match_is_in(dialog, qapp):
    page = dialog._sports_page
    assert page.advanced_box.isHidden()
    dialog._help.find("clock evidence")
    _settle(qapp)
    assert dialog._nav.label(dialog._nav.current_row()) == "Sports"
    assert page.advanced_box.isVisible()
    assert _tints(dialog, dialog._nav.current_row())


# ── Q12 ─────────────────────────────────────────────────────────────────

def test_hide_after_says_what_it_counts(dialog):
    spin = dialog._signal_streak_spin
    spin.setValue(2)
    assert spin.text() == "2 checks"
    spin.setValue(1)
    assert spin.text() == "1 check"


def test_checkbox_extras_join_their_checkbox(dialog):
    """"Pre-buffer before playing  Wait: 10 s" is ONE setting, not two."""
    entries = dialog._help.entries(_index(dialog, "Playback"))
    pre = [e for e in entries if e.title.startswith("Pre-buffer")]
    assert len(pre) == 1 and pre[0].extras
    assert not any(e.title == "Wait" for e in entries)
    assert isinstance(pre[0].control, QCheckBox) and not isinstance(pre[0].extras[0], QComboBox)
