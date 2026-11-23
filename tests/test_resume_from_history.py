"""Resuming from History, and a rewatch that keeps its place (owner, 2026-11-23).

The owner's evening with The Outer Limits S04E01: it was finished and in History;
replaying it started over (right for a finished episode), but two seconds in the
save un-marked it, it fell under "Show in History after", and History dropped it.
And History, the Watch Queue and Favorites never resumed an episode at all:
``play_episode_by_id`` always started at 0, whatever Settings ▸ Playback said.

Now a rewatch keeps the watched mark and saves its position; every row play
resumes as the setting says; History's right-click plays the episode the row
names and offers Resume / Play from Beginning for it; and beside Resume the
details pane's other button says "Start over".
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from streamselect.core.playback_resume import default_start_seconds


@pytest.fixture
def db(tmp_path):
    from streamselect.core.database import Database

    database = Database(f"sqlite:///{tmp_path / 'resume.db'}")
    database.create_tables()
    yield database
    database.close()


def _show(db, *, progress=0, completed=False) -> str:
    from streamselect.core.database import ChannelDB, EpisodeDB, SeasonDB

    with db.session_scope() as session:
        session.add(ChannelDB(id="show", source_id="s1", provider_id="p1", name="The Show",
                              media_type="series", last_played=datetime.now()))
        session.add(SeasonDB(id="s1_s04", series_id="s1", provider_id="p1", season_number=4, name="S4"))
        session.add(EpisodeDB(id="e1", season_id="s1_s04", series_id="s1", provider_id="p1",
                              episode_id="1", episode_num=1, season_num=4, title="Criminal Nature",
                              stream_url="http://example.com/e1", last_played=datetime.now(),
                              last_played_via="manual", watch_progress=progress,
                              watch_completed=completed, is_watched=completed))
    return "e1"


class TestTheStartPosition:

    def test_resume_mode_starts_at_the_saved_position(self):
        assert default_start_seconds(987, "resume") == 987

    def test_beginning_mode_starts_at_zero(self):
        assert default_start_seconds(987, "beginning") == 0

    def test_nothing_saved_starts_at_zero(self):
        assert default_start_seconds(None, "resume") == 0


def _player(db, mode="resume"):
    from streamselect.gui.main_window_series_playback import _SeriesPlaybackMixin
    from tests.conftest import wire_status_method

    host = _SeriesPlaybackMixin.__new__(_SeriesPlaybackMixin)
    host.db = db
    host.status_bar = None
    wire_status_method(host)
    host.config = SimpleNamespace(playback_resume_mode=mode)
    host.played = []
    host.play_episode = lambda episode, start_seconds=0, **kw: host.played.append((episode.id, start_seconds))
    return host


class TestRowPlaysResume:

    def test_a_row_play_resumes_where_you_left_off(self, db):
        host = _player(db)
        host.play_episode_by_id(_show(db, progress=987))
        assert host.played == [("e1", 987)]

    def test_start_from_beginning_setting_is_honoured(self, db):
        host = _player(db, mode="beginning")
        host.play_episode_by_id(_show(db, progress=987))
        assert host.played == [("e1", 0)]

    def test_a_menu_choice_overrides_the_setting(self, db):
        host = _player(db, mode="beginning")
        host.play_episode_by_id(_show(db, progress=987), start_seconds=987)
        assert host.played == [("e1", 987)]


class TestARewatchKeepsItsPlace:

    def test_starting_a_finished_episode_over_keeps_it_watched_and_in_history(self, db):
        from streamselect.core.repositories import RepositoryFactory
        from streamselect.core.repositories.dtos import build_history_dtos

        ep = _show(db, completed=True)
        with db.session_scope() as session:
            RepositoryFactory(session).episodes.record_watch_progress(ep, 2, 2640)
        with db.session_scope() as session:
            repos = RepositoryFactory(session)
            row = repos.episodes.get_by_id(ep)
            assert row.watch_completed and row.is_watched and row.watch_progress == 2
            names = {d.name for d in build_history_dtos(repos, min_seconds=300)}
        assert "The Show" in names, "two seconds into a rewatch must not drop it from History"


class _MenuHost:
    """The History mixin's two menu hooks, on a real database."""

    def __init__(self, db):
        from streamselect.gui.main_window_history import _HistoryMixin
        self.db = db
        self.calls = []
        self._with = lambda ctx: _HistoryMixin._with_history_episode(self, ctx)
        self._handlers = lambda ctx: _HistoryMixin._history_episode_handlers(self, ctx)

    def play_from_history_id(self, cid, ep):
        self.calls.append(("history", cid, ep))

    def play_episode_by_id(self, ep, start_seconds=None):
        self.calls.append(("episode", ep, start_seconds))


def _history_ctx(**kw):
    from streamselect.gui.channel_menu import ChannelMenuContext
    return ChannelMenuContext(channel_ids=["show"], surface="history", media_type="series", **kw)


class TestTheHistoryMenu:

    def test_the_menu_learns_the_named_episodes_position(self, db):
        ctx = _MenuHost(db)._with(_history_ctx(entry_id=_show(db, progress=987)))
        assert ctx.watch_progress == 987

    def test_play_resume_and_beginning_all_target_the_named_episode(self, db):
        host = _MenuHost(db)
        ctx = host._with(_history_ctx(entry_id=_show(db, progress=987)))
        handlers = host._handlers(ctx)
        handlers["play"]()
        handlers["resume_from"]()
        handlers["play_from_beginning"]()
        assert host.calls == [("history", "show", "e1"), ("episode", "e1", 987), ("episode", "e1", 0)]

    def test_a_row_with_no_episode_keeps_the_shared_handlers(self, db):
        assert _MenuHost(db)._handlers(_history_ctx()) == {}

    @pytest.mark.parametrize("mode, wanted", [("resume", "Play from Beginning"), ("beginning", "Resume from")])
    def test_the_menu_offers_the_other_choice_for_the_episode(self, qapp, mode, wanted):
        from streamselect.gui.channel_menu import build_channel_menu
        ctx = _history_ctx(entry_id="e1", watch_progress=987, playback_resume_mode=mode)
        from streamselect.gui.channel_menu_layouts import SURFACE_LAYOUTS
        handlers = {k: (lambda: None) for k in SURFACE_LAYOUTS["history"] if k != "sep"}
        menu = build_channel_menu(ctx, handlers)
        texts = [a.text() for a in menu.actions()]
        assert any(t.startswith(wanted) for t in texts), texts
        if mode == "resume":
            assert "Play from 16:27" in texts, "Play says it resumes, and from where"


class TestStartOver:

    def _bar(self, qapp, owned_widgets):
        from streamselect.core.config import Config
        from streamselect.gui.details_actions import _ActionBar
        bar = owned_widgets.own(_ActionBar(Config()))
        bar.resize(420, 80)
        bar.show()
        qapp.processEvents()
        return bar

    def test_beside_resume_the_play_button_says_start_over(self, qapp, owned_widgets):
        bar = self._bar(qapp, owned_widgets)
        bar.enter_episode_mode("S04E01")
        assert bar.play_button.text() == "Play Episode: S04E01"
        bar.set_resume(True, 987)
        qapp.processEvents()
        assert bar.play_button.text() == "Start over"
        assert bar.resume_button.text() == "Resume 16:27"
        assert "S04E01" in bar.play_button.toolTip()
        fm = bar.play_button.fontMetrics()
        assert fm.horizontalAdvance(bar.play_button.text()) < bar.play_button.width(), "the label fits"

    def test_without_resume_it_goes_back_to_naming_the_episode(self, qapp, owned_widgets):
        bar = self._bar(qapp, owned_widgets)
        bar.enter_episode_mode("S04E01")
        bar.set_resume(True, 987)
        bar.set_resume(False)
        assert bar.play_button.text() == "Play Episode: S04E01"

    def test_a_new_episode_starts_without_the_last_ones_resume(self, qapp, owned_widgets):
        bar = self._bar(qapp, owned_widgets)
        bar.enter_episode_mode("S04E01")
        bar.set_resume(True, 987)
        bar.enter_episode_mode("S04E02")
        assert bar.play_button.text() == "Play Episode: S04E02" and not bar.resume_button.isVisibleTo(bar)
