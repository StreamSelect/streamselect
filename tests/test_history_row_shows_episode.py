"""In History, the episode chip opens the episode; the rest of the row, the series.

Owner, 2026-11-23: "the history item should only open the episode in the details
panel if the episode chip in the history line item is clicked, if the series name is
clicked, the details panel should open to the series details." The S04E01 chip is a
real button (pointer cursor, tooltip) whose click selects the row and emits
``episodeSelected``; a click anywhere else selects the row as before and emits
``itemSelected`` with the channel, which opens the series. The episode opens over
its series through the playback menu's shared path (``show_episode_details_by_id``).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest

from streamselect.core.config import Config
from streamselect.core.repositories.dtos import HistoryDTO


def _section(qapp, tmp_path, owned_widgets):
    from streamselect.gui.sidebar.history import HistorySection
    sec = owned_widgets.own(HistorySection(Config(config_dir=tmp_path), db=None))
    rows = [HistoryDTO(id="show", name="The Show", media_type="series", episode_code="S04E01",
                       episode_id="e1", last_played=datetime.now() - timedelta(minutes=5),
                       detected_title="The Show"),
            HistoryDTO(id="film", name="Arrival", media_type="movie", episode_code=None,
                       last_played=datetime.now() - timedelta(minutes=6), detected_title="Arrival",
                       detected_year="2016")]
    sec.refresh = lambda: None
    sec.resize(320, 300)
    sec.show()
    sec._populate_rows(rows)
    qapp.processEvents()
    got = {"series": [], "episode": []}
    sec.itemSelected.connect(lambda cid: got["series"].append(cid))
    sec.episodeSelected.connect(lambda ep: got["episode"].append(ep))
    return sec, got


def _row(sec, cid):
    lst = sec.history_list
    item = next(lst.item(i) for i in range(lst.count()) if lst.item(i).data(Qt.ItemDataRole.UserRole) == cid)
    return item, lst.itemWidget(item)


def _chip(row):
    from PyQt6.QtWidgets import QPushButton
    return next(b for b in row.findChildren(QPushButton) if b.text() == "S04E01")


def test_clicking_the_episode_chip_opens_the_episode(qapp, tmp_path, owned_widgets):
    sec, got = _section(qapp, tmp_path, owned_widgets)
    item, row = _row(sec, "show")
    chip = _chip(row)
    assert chip.isVisibleTo(sec) and "details pane" in chip.toolTip()
    assert chip.cursor().shape() == Qt.CursorShape.PointingHandCursor
    # Qt's own hit test: a press there reaches the chip (a mouse-transparent row
    # would hand it to the list, and the chip could never be clicked).
    lst = sec.history_list
    centre = chip.mapTo(lst.viewport(), chip.rect().center())
    assert lst.viewport().childAt(centre) is chip
    QTest.mouseClick(chip, Qt.MouseButton.LeftButton)
    assert got == {"series": [], "episode": ["e1"]}, "the episode only, not the series first"
    assert sec.history_list.currentItem() is item, "and its row is selected"


def test_clicking_the_series_name_opens_the_series(qapp, tmp_path, owned_widgets):
    sec, got = _section(qapp, tmp_path, owned_widgets)
    _item, row = _row(sec, "show")
    lst = sec.history_list
    # A click on the series name, well left of the chips.
    at = row.mapTo(lst.viewport(), QPoint(30, row.height() // 2))
    QTest.mouseClick(lst.viewport(), Qt.MouseButton.LeftButton, pos=at)
    # (Row activation announces a click and a selection change alike; what matters is
    # that the series, and only the series, was asked for.)
    assert set(got["series"]) == {"show"} and got["episode"] == []


def test_a_film_row_has_no_clickable_chip(qapp, tmp_path, owned_widgets):
    from PyQt6.QtWidgets import QPushButton
    sec, _got = _section(qapp, tmp_path, owned_widgets)
    _item, row = _row(sec, "film")
    year = next(b for b in row.findChildren(QPushButton) if b.text() == "2016")
    assert year.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


@pytest.fixture
def db(tmp_path):
    from streamselect.core.database import Database
    database = Database(f"sqlite:///{tmp_path / 'h.db'}")
    database.create_tables()
    yield database
    database.close()


def test_the_episode_is_laid_over_its_series_in_the_real_pane(db, qapp, owned_widgets):
    """End to end through the shared path: series first, then the episode on top."""
    from unittest.mock import MagicMock

    from streamselect.core.database import ChannelDB, EpisodeDB, SeasonDB
    from streamselect.core.repositories import RepositoryFactory
    from streamselect.gui.details_pane import DetailsPaneWidget
    from streamselect.gui.main_window_menu_actions import _MenuActionsMixin
    from streamselect.gui.main_window_series import _SeriesMixin

    with db.session_scope() as s:
        s.add(ChannelDB(id="show", source_id="s1", provider_id="p1", name="The Show",
                        media_type="series", last_played=datetime.now()))
        s.add(SeasonDB(id="s1_s04", series_id="s1", provider_id="p1", season_number=4, name="S4"))
        s.add(EpisodeDB(id="e1", season_id="s1_s04", series_id="s1", provider_id="p1", episode_id="1",
                        episode_num=1, season_num=4, title="Criminal Nature",
                        stream_url="http://example.com/e1", watch_progress=987, watch_percent=37))
    cache = MagicMock()
    cache.get_image_sync.return_value = None
    pane = owned_widgets.own(DetailsPaneWidget(Config(), cache, db=None))

    host = SimpleNamespace(details_pane=pane, status=lambda *a, **k: None, _load_stream_info=lambda _id: None)

    def run_query(fn, on_result, **_kw):
        with db.session_scope() as s:
            on_result(fn(RepositoryFactory(s)))

    def show_channel(cid, on_shown=None):
        with db.session_scope() as s:
            ch = s.get(ChannelDB, cid)
            pane.show_channel(SimpleNamespace(**{c.name: getattr(ch, c.name) for c in ChannelDB.__table__.columns}))
        if on_shown:
            on_shown()

    host._run_query = run_query
    host.show_channel_details_by_id = show_channel
    host._episode_display_title = lambda ep: _SeriesMixin._episode_display_title(host, ep)
    host._on_playing_episode_read = lambda found: _MenuActionsMixin._on_playing_episode_read(host, found)
    _MenuActionsMixin.show_episode_details_by_id(host, "e1")

    assert pane.current_episode is not None and pane.current_episode.id == "e1"
    assert pane._action_bar.play_button.text() == "Start over"
    assert pane._action_bar.resume_button.text() == "Resume 16:27"
