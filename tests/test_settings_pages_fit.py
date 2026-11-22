"""Every Settings page fits its column at the dialog's minimum width (owner, 2026-11-22).

The Sports page was squeezed: each page sat bare in the dialog's stack, so a page wider
than the centre column was laid out BELOW its minimum width. Labels were drawn under
their value boxes, values were cut off ("36 h ahe"), and the tallest page's height became
the whole dialog's minimum (824 px). Pages now scroll in their own area, the Sports rows
stack their note and Reset under the value, and long labels wrap at a capped column.

These assert the painted geometry, not the widget tree.
"""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QAbstractSpinBox, QApplication, QFormLayout, QLabel, QScrollArea


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialog(qapp):
    from streamselect.core.config import Config
    from streamselect.gui.settings_dialog import SettingsDialog

    dlg = SettingsDialog(Config())
    dlg.resize(dlg.minimumWidth(), 600)
    dlg.show()
    qapp.processEvents()
    yield dlg
    from tests.conftest import destroy_widget
    destroy_widget(dlg)


def _settle(qapp):
    for _ in range(5):
        qapp.processEvents()


def test_no_page_scrolls_sideways_at_the_minimum_width(dialog, qapp):
    for row in range(dialog._nav.count()):
        dialog._nav.set_current_row(row)
        _settle(qapp)
        area = dialog._nav.stack.currentWidget()
        assert isinstance(area, QScrollArea)
        name = dialog._nav.section_list.item(row).text()
        assert area.widget().minimumSizeHint().width() <= area.viewport().width(), (
            f"{name}: page needs {area.widget().minimumSizeHint().width()} px, "
            f"column gives {area.viewport().width()}")


def test_sports_labels_end_before_their_values_and_values_are_not_cut(dialog, qapp):
    dialog.select_section_by_label("Sports")
    page = dialog._sports_page
    page.select_sport("hockey")
    page.edit("still_on_adds", 20)          # a row showing its note and Reset
    _settle(qapp)
    checked = 0
    for form in page.findChildren(QFormLayout):
        for i in range(form.rowCount()):
            label = form.itemAt(i, QFormLayout.ItemRole.LabelRole)
            field = form.itemAt(i, QFormLayout.ItemRole.FieldRole)
            if not (label and field and label.widget() and field.widget()):
                continue
            lw, fw = label.widget(), field.widget()
            if not (isinstance(lw, QLabel) and lw.isVisible() and fw.isVisible()):
                continue
            left = lw.mapTo(page, lw.rect().topRight()).x()
            right = fw.mapTo(page, fw.rect().topLeft()).x()
            assert left < right, f"{lw.text()!r} is drawn under its value"
            checked += 1
    assert checked >= 8
    for spin in page.findChildren(QAbstractSpinBox):
        if spin.isVisible():
            assert spin.width() >= spin.minimumSizeHint().width(), \
                f"{spin.text()!r} is cut off ({spin.width()} < {spin.minimumSizeHint().width()})"


def test_the_tallest_page_does_not_set_the_dialogs_minimum_height(dialog):
    assert dialog.minimumSizeHint().height() < 400, (
        f"dialog cannot be shorter than {dialog.minimumSizeHint().height()} px")


def test_the_section_list_shows_every_label_whole(dialog):
    nav = dialog._nav.section_list
    for i in range(nav.count()):
        assert nav.visualItemRect(nav.item(i)).width() <= nav.viewport().width()
        assert nav.sizeHintForColumn(0) <= nav.viewport().width(), nav.item(i).text()
