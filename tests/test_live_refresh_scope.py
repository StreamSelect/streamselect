"""A live-only refresh does live-only work, and says so.

Measured on one source (54k live, 245k movies/series): the scheduled 3-hourly
live-only refresh fetched just the live list, then re-categorized 286,659 rows
and re-parsed and re-tagged all 298,802 — movies and series included. It also
stamped the source as FULLY refreshed (the call site never passed its kind), so
the weekly movie/series refresh never came due. And it forced an EPG download
every time: at launch that landed three minutes after the launch's own fetch.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from streamselect.core.database import ChannelDB, ContentTagDB, Database, ProviderDB
from streamselect.core.models import Channel, MediaType, Provider, StreamQuality
from streamselect.core.provider_loader import ProviderLoadThread
from streamselect.gui.main_window_providers import _ProviderMixin
from streamselect.gui.refresh_queue_manager import RefreshQueueManager

PID = "p"


@pytest.fixture()
def db(tmp_path):
    d = Database(f"sqlite:///{tmp_path / 'scope.db'}")
    d.create_tables()
    yield d
    d.close()


def _provider() -> Provider:
    p = Provider.__new__(Provider)
    p.id, p.name, p.type, p.url = PID, "P", "xtream", "http://example.com"
    p.username, p.password, p.urls = "u", "p", []
    return p


def _load(db, kind):
    live = Channel(id=f"{PID}_1", source_id="1", provider_id=PID, name="UK| SKY NEWS HD",
                   stream_url="http://example.com/live/1", category="UK| NEWS",
                   category_id="1", media_type=MediaType.LIVE, quality=StreamQuality.HD,
                   raw_data={})
    plugin = MagicMock()
    plugin.fetch_channels = AsyncMock(return_value=[live])
    plugin.fetch_account_info = None
    thread = ProviderLoadThread(_provider(), db, kind=kind)
    with patch("streamselect.core.provider_loader.get_provider", return_value=plugin):
        asyncio.run(thread.load_provider())


def test_live_only_leaves_movie_rows_unparsed_and_untagged(db):
    with db.session_scope() as s:
        s.add(ChannelDB(id=f"{PID}_m", source_id="m", provider_id=PID,
                        name="EN - Some Movie (2020)", category="EN| DRAMA",
                        stream_url="http://example.com/movie/m", media_type="movie"))
    _load(db, "live_only")
    with db.session_scope(commit=False) as s:
        movie = s.query(ChannelDB).filter_by(id=f"{PID}_m").one()
        live = s.query(ChannelDB).filter_by(id=f"{PID}_1").one()
        assert live.detected_prefix == "UK"
        assert movie.detected_title is None and movie.detected_prefix is None
        assert movie.tag_fingerprint is None
        assert not s.query(ContentTagDB).filter_by(channel_key=movie.channel_key).count()


def _finished_host():
    host = _ProviderMixin.__new__(_ProviderMixin)
    host.active_threads, host.refreshing_providers = [], set()
    host._epg_fetch_after_add = set()
    for name in ("_sync_empty_state", "_mark_catalog_refreshed",
                 "_refresh_provider_dependent_views", "_maybe_refresh_provider_epg"):
        setattr(host, name, MagicMock())
    host.epg_manager = MagicMock()
    return host


@pytest.mark.parametrize("kind, due", [("live_only", False), ("full", True)])
def test_the_finished_refresh_stamps_its_own_kind(kind, due):
    host = _finished_host()
    thread = SimpleNamespace(kind=kind, fetch_epg=due, prefix_stats=None)
    host._on_queue_refresh_finished(PID, True, "", thread)
    host._mark_catalog_refreshed.assert_called_once_with(PID, kind)
    host._maybe_refresh_provider_epg.assert_called_once_with(PID, due)


def test_epg_not_due_is_not_fetched(db):
    with db.session_scope() as s:
        s.add(ProviderDB(id=PID, name="P", type="xtream", url="http://example.com",
                         is_active=True, epg_enabled=True))
    host = _ProviderMixin.__new__(_ProviderMixin)
    host.db, host.epg_manager = db, MagicMock()
    host.epg_manager.effective_epg_url.return_value = "http://example.com/epg.xml"
    host._on_provider_epg_refresh = MagicMock()
    host._maybe_refresh_provider_epg(PID, False)
    host._on_provider_epg_refresh.assert_not_called()


@pytest.mark.parametrize("kind, needs, expected", [
    ("live_only", False, False),  # the guide is current: no fetch, no EPG steps
    ("live_only", True, True),
    ("full", False, True),        # a full refresh still pulls the guide
])
def test_queue_decides_the_epg_step_once_by_kind(db, kind, needs, expected):
    with db.session_scope() as s:
        s.add(ProviderDB(id=PID, name="P", type="xtream", url="http://example.com",
                         is_active=True, epg_enabled=True))
    em = MagicMock()
    em.effective_epg_url.return_value = "http://example.com/epg.xml"
    em.needs_refresh.return_value = needs
    manager = RefreshQueueManager(db, MagicMock(), MagicMock(), parent=None)
    with patch.object(RefreshQueueManager, "parent", return_value=SimpleNamespace(epg_manager=em)):
        assert manager._provider_has_epg(PID, kind) is expected


def test_the_overview_names_a_live_only_refresh():
    from streamselect.gui.refresh_queue_manager import _QueueEntry

    manager = RefreshQueueManager(MagicMock(), MagicMock(), MagicMock(), parent=None)
    manager._queue = [_QueueEntry(provider_id="a", provider_name="Src A", kind="live_only"),
                      _QueueEntry(provider_id="b", provider_name="Src B")]
    labels = [label for label, _status in manager._build_overview_steps()]
    assert labels == ["Src A  (live only)", "Src B"]
