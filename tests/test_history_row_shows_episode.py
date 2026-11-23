"""Selecting a History row that names an episode shows that episode (owner, 2026-11-23).

"Clicking on the history brings up the series to browse, not the episode itself.
Clicking on the episode chip should bring up the episode directly into the details
panel." The row is about the episode it names (its S04E01 chip), so selecting it
lays that episode over its series in the details pane, through the same path the
playback menu's "show what's playing" uses. A movie or live row is unchanged.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QListWidget, QListWidgetItem

from streamselect.gui.sidebar.history import _ROLE_EPISODE_ID


def _host(rows, owned_widgets):
    from streamselect.gui.main_window_history import _HistoryMixin
    lst = owned_widgets.own(QListWidget())
    for cid, ep in rows:
        item = QListWidgetItem(lst)
        item.setData(Qt.ItemDataRole.UserRole, cid)
        item.setData(_ROLE_EPISODE_ID, ep)
    host = SimpleNamespace(sidebar_sections={"history": SimpleNamespace(history_list=lst)}, shown=[])
    host.show_episode_details_by_id = lambda ep: host.shown.append(("episode", ep))
    host.show_channel_details_by_id = lambda cid: host.shown.append(("channel", cid))
    host.select = lambda row: (lst.setCurrentRow(row),
                               _HistoryMixin.show_history_row_details(host, lst.item(row).data(Qt.ItemDataRole.UserRole)))
    return host, lst


def test_a_show_row_opens_the_episode_it_names(qapp, owned_widgets):
    host, _lst = _host([("show", "e1"), ("movie", "")], owned_widgets)
    host.select(0)
    assert host.shown == [("episode", "e1")]


def test_a_movie_row_still_opens_its_channel(qapp, owned_widgets):
    host, _lst = _host([("show", "e1"), ("movie", "")], owned_widgets)
    host.select(1)
    assert host.shown == [("channel", "movie")]


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

    from streamselect.core.config import Config
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
