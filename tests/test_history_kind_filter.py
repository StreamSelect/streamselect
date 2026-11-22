"""History: show or hide Live channels, Movies and Series (owner, 2026-11-22).

Most live entries in History are event slots whose names change with each game
("02 - 5pm Sabres at Lightning"), and they crowd out the films and episodes. The ⋯
menu gets a "Show" group of three ticks, remembered across launches; the list says
what it is leaving out, so a shorter History never reads as lost history.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from streamselect.core.config import Config
from streamselect.core.repositories.dtos import HistoryDTO
from streamselect.gui.sidebar.history import HistorySection
from tests.conftest import destroy_widget

_ROLE_BUCKET = Qt.ItemDataRole.UserRole + 8


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _dto(cid, title, media, minutes):
    return HistoryDTO(id=cid, name=title, media_type=media, episode_code=None,
                      last_played=datetime.now() - timedelta(minutes=minutes),
                      detected_title=title)


ROWS = [
    _dto("l1", "02 - 5pm Sabres at Lightning", "live", 5),
    _dto("m1", "Arrival", "movie", 6),
    _dto("l2", "NHL NETWORK", "live", 7),
    _dto("s1", "The Outer Limits", "series", 8),
]


def _make(qapp, tmp_path, hidden=()):
    config = Config(config_dir=tmp_path)
    config.history_hidden_kinds = list(hidden)
    sec = HistorySection(config, db=None)
    sec.refresh = lambda: (sec.history_list.clear(), sec._populate_rows(list(ROWS)))
    sec.resize(280, 400)
    sec.show()
    sec._populate_rows(list(ROWS))
    QApplication.processEvents()
    return sec


def _row_ids(sec):
    lst = sec.history_list
    return [lst.item(i).data(Qt.ItemDataRole.UserRole) for i in range(lst.count())
            if lst.item(i).data(Qt.ItemDataRole.UserRole)]


def _first_widget_text(sec):
    lst = sec.history_list
    w = lst.itemWidget(lst.item(0))
    return w.text() if hasattr(w, "text") else ""


def test_the_menu_offers_the_three_kinds_all_shown(qapp, tmp_path):
    sec = _make(qapp, tmp_path)
    try:
        labels = {a.text(): a for a in sec._overflow_menu.actions() if a.isCheckable()}
        assert set(labels) == {"Live channels", "Movies", "Series"}
        assert all(a.isChecked() for a in labels.values())
        assert _row_ids(sec) == ["l1", "m1", "l2", "s1"]
    finally:
        destroy_widget(sec)


def test_hiding_live_leaves_it_out_says_so_and_is_remembered(qapp, tmp_path):
    sec = _make(qapp, tmp_path)
    try:
        sec._kind_actions["live"].trigger()          # untick, as a click does
        QApplication.processEvents()
        assert _row_ids(sec) == ["m1", "s1"]
        assert sec.config.history_hidden_kinds == ["live"]
        assert _first_widget_text(sec) == "Live channels hidden"
        lst = sec.history_list
        note = lst.visualItemRect(lst.item(0))
        first_row = next(i for i in range(lst.count()) if lst.item(i).data(Qt.ItemDataRole.UserRole))
        assert note.bottom() <= lst.visualItemRect(lst.item(first_row)).top(), "the note leads the list"
        headings = [lst.itemWidget(lst.item(i)) for i in range(lst.count())
                    if lst.item(i).data(_ROLE_BUCKET) is not None]
        assert sum(int(h.count_label.text()) for h in headings) == 2, "group counts follow what is shown"
        assert sec.item_count() == 2, "the header count follows what is shown"
    finally:
        destroy_widget(sec)


def test_a_new_launch_keeps_live_hidden_and_ticking_it_brings_it_back(qapp, tmp_path):
    sec = _make(qapp, tmp_path, hidden=["live"])
    try:
        assert not sec._kind_actions["live"].isChecked()
        assert _row_ids(sec) == ["m1", "s1"]
        sec._kind_actions["live"].trigger()
        QApplication.processEvents()
        assert _row_ids(sec) == ["l1", "m1", "l2", "s1"]
        assert sec.config.history_hidden_kinds == []
        assert _first_widget_text(sec) != "Live channels hidden"
    finally:
        destroy_widget(sec)
