"""History lists what was watched — not what was skipped through or walked back.

Owner, 2026-11-22, on a queue that auto-advanced through eleven episodes overnight:
answering No to "Did you watch them?" set every episode back to unwatched, yet the
show stayed in History naming S04E12 — an episode that played for 34 seconds.
Two causes: No cleared the watch fields but kept each episode's ``last_played``,
and History listed a show and named its episode by ``last_played`` alone.

Now an episode or movie counts in History once finished or played at least
Settings ▸ Sidebar "Show in History after" (default 5 min); a live channel once
played; and answering No forgets the play entirely.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

FIVE_MIN = 300


@pytest.fixture
def db(tmp_path):
    """File-backed, not ``:memory:`` — pooled connections must share tables."""
    from streamselect.core.database import Database

    database = Database(f"sqlite:///{tmp_path / 'history.db'}")
    database.create_tables()
    yield database
    database.close()


def _channel(db, name, media_type, *, progress=0, completed=False, source_id=None) -> str:
    from streamselect.core.database import ChannelDB

    cid = str(uuid.uuid4())
    with db.session_scope() as session:
        session.add(ChannelDB(id=cid, source_id=source_id or cid, provider_id="p1", name=name,
                              media_type=media_type, last_played=datetime.now(),
                              watch_progress=progress, watch_completed=completed))
    return cid


def _episode(db, series_id, num, *, ago_min, progress=0, completed=False) -> str:
    from streamselect.core.database import EpisodeDB, SeasonDB

    season = f"{series_id}_s04"
    ep_id = f"{series_id}_e{num}"
    with db.session_scope() as session:
        if not session.get(SeasonDB, season):
            session.add(SeasonDB(id=season, series_id=series_id, provider_id="p1",
                                 season_number=4, name="Season 4"))
        session.add(EpisodeDB(id=ep_id, season_id=season, series_id=series_id, provider_id="p1",
                              episode_id=str(num), episode_num=num, season_num=4,
                              title=f"Episode {num}", stream_url="http://example.com/ep",
                              last_played=datetime.now() - timedelta(minutes=ago_min),
                              last_played_via="queue", watch_progress=progress,
                              watch_completed=completed, is_watched=completed))
    return ep_id


def _history(db, min_seconds=FIVE_MIN):
    from streamselect.core.repositories import RepositoryFactory
    from streamselect.core.repositories.dtos import build_history_dtos

    with db.session_scope() as session:
        return {d.name: d for d in build_history_dtos(RepositoryFactory(session), limit=50,
                                                       min_seconds=min_seconds)}


def _walk_back(db, ids):
    from streamselect.core.repositories import RepositoryFactory

    with db.session_scope() as session:
        RepositoryFactory(session).episodes.mark_watched_bulk(ids, False, forget_play=True)


class TestTheOuterLimitsNight:
    """The owner's case, as stored: E1-E11 auto-advanced and walked back, E12 played 34 s."""

    def _seed(self, db):
        _channel(db, "The Outer Limits", "series", source_id="tol")
        run = [_episode(db, "tol", n, ago_min=600 - 40 * n, completed=True) for n in range(1, 12)]
        _episode(db, "tol", 12, ago_min=5, progress=34)
        return run

    def test_walked_back_and_skipped_episodes_leave_the_show_out(self, db):
        run = self._seed(db)
        assert "The Outer Limits" in _history(db), "before the answer the auto-marked run counts"
        _walk_back(db, run)
        assert "The Outer Limits" not in _history(db)

    def test_one_episode_really_watched_keeps_the_show_and_is_the_one_named(self, db):
        run = self._seed(db)
        _walk_back(db, run[1:])           # the first episode was really watched
        row = _history(db)["The Outer Limits"]
        assert row.episode_code == "S04E01", "names the episode watched, not the 34 s one"
        assert row.episode_id == run[0]


class TestWalkingBackForgetsThePlay:

    def test_no_clears_last_played(self, db):
        from streamselect.core.database import EpisodeDB

        _channel(db, "Show", "series", source_id="s1")
        ep = _episode(db, "s1", 1, ago_min=30, completed=True)
        _walk_back(db, [ep])
        with db.session_scope() as session:
            row = session.get(EpisodeDB, ep)
            assert row.last_played is None and not row.watch_completed

    def test_a_walked_back_episode_is_out_even_when_the_setting_is_zero(self, db):
        """0 min lists everything started; a walked-back episode was never watched."""
        _channel(db, "Show", "series", source_id="s1")
        ep = _episode(db, "s1", 1, ago_min=30, completed=True)
        _walk_back(db, [ep])
        assert "Show" not in _history(db, min_seconds=0)

    def test_mark_unwatched_from_a_menu_keeps_the_play_time(self, db):
        """Only the walk-back forgets the play; the plain unmark is unchanged."""
        from streamselect.core.database import EpisodeDB
        from streamselect.core.repositories import RepositoryFactory

        _channel(db, "Show", "series", source_id="s1")
        ep = _episode(db, "s1", 1, ago_min=30, completed=True)
        with db.session_scope() as session:
            RepositoryFactory(session).episodes.mark_watched_bulk([ep], False)
        with db.session_scope() as session:
            assert session.get(EpisodeDB, ep).last_played is not None


class TestTheThreshold:

    @pytest.mark.parametrize("progress, listed", [(34, False), (FIVE_MIN - 1, False),
                                                  (FIVE_MIN, True), (1800, True)])
    def test_an_episode_counts_from_the_setting(self, db, progress, listed):
        _channel(db, "Show", "series", source_id="s1")
        _episode(db, "s1", 1, ago_min=10, progress=progress)
        assert ("Show" in _history(db)) is listed

    def test_a_finished_episode_counts_though_its_resume_point_is_zero(self, db):
        _channel(db, "Show", "series", source_id="s1")
        _episode(db, "s1", 1, ago_min=10, progress=0, completed=True)
        assert "Show" in _history(db)

    @pytest.mark.parametrize("progress, completed, listed", [(120, False, False), (600, False, True),
                                                             (0, True, True)])
    def test_a_movie_counts_the_same_way(self, db, progress, completed, listed):
        _channel(db, "A Movie", "movie", progress=progress, completed=completed)
        assert ("A Movie" in _history(db)) is listed

    def test_a_live_channel_counts_once_played(self, db):
        _channel(db, "A Live Channel", "live")
        assert "A Live Channel" in _history(db)

    def test_full_history_follows_the_same_rule(self, db):
        """The trail map reads the same query, so the two lists cannot disagree."""
        from streamselect.gui.trail_map_data import load_history_ids

        kept = _channel(db, "Long", "movie", progress=900)
        _channel(db, "Short", "movie", progress=30)
        with db.session_scope() as session:
            assert load_history_ids(session, min_seconds=FIVE_MIN) == [kept]

    def test_the_setting_is_read_in_minutes(self):
        from streamselect.core.config import Config
        from streamselect.core.history_buckets import history_min_seconds

        c = Config()
        assert c.history_min_minutes == 5
        c.history_min_minutes = 12
        assert history_min_seconds(c) == 720


def test_the_setting_is_on_the_sidebar_page_and_saves(qtbot, monkeypatch):
    """Rendered on Settings ▸ Sidebar under History, showing its unit; OK saves it."""
    from PyQt6.QtWidgets import QLabel
    from streamselect.core.config import Config
    from streamselect.gui.settings_dialog import SettingsDialog

    monkeypatch.setattr(Config, "save", lambda *a, **k: None)
    cfg = Config()
    dlg = SettingsDialog(cfg)
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.select_section_by_label("Sidebar")
    qtbot.waitUntil(lambda: dlg._history_min_spin.isVisible())
    spin = dlg._history_min_spin
    assert spin.text() == "5 min"
    assert spin.toolTip(), "every setting explains itself (Settings help column)"
    label = next(w for w in dlg.findChildren(QLabel) if w.text() == "Show in History after:")
    assert label.isVisible()
    lg, sg = label.mapTo(dlg, label.rect().center()), spin.mapTo(dlg, spin.rect().center())
    assert abs(lg.y() - sg.y()) <= 4 and lg.x() < sg.x(), "label and box share one form row"
    spin.setValue(12)
    dlg._save_values()
    assert cfg.history_min_minutes == 12


class TestTheFurthestPointCounts:
    """Owner, 2026-11-23: watched minutes into S04E02, jumped back to the opening,
    stopped at 0:55 — and History left it out, judging by where the play ended."""

    def test_jumping_back_keeps_the_furthest_point_and_the_resume_point(self, db):
        from streamselect.core.database import EpisodeDB
        from streamselect.core.repositories import RepositoryFactory

        _channel(db, "The Show", "series", source_id="s1")
        ep = _episode(db, "s1", 2, ago_min=1)
        with db.session_scope() as session:
            repo = RepositoryFactory(session).episodes
            for pos in (60, 300, 540, 20, 55):       # watched to 9:00, back to the start
                repo.record_watch_progress(ep, pos, 2640)
        with db.session_scope() as session:
            row = session.get(EpisodeDB, ep)
            assert (row.watch_progress, row.furthest_position) == (55, 540)
        assert "The Show" in _history(db), "nine minutes in counts, wherever it stopped"

    def test_a_movie_too(self, db):
        from streamselect.core.repositories import RepositoryFactory
        cid = _channel(db, "A Movie", "movie")
        with db.session_scope() as session:
            repo = RepositoryFactory(session).channels
            repo.record_watch_progress(cid, 900, 6000)
            repo.record_watch_progress(cid, 40, 6000)
        assert "A Movie" in _history(db)

    def test_marking_it_unwatched_forgets_the_furthest_point(self, db):
        from streamselect.core.repositories import RepositoryFactory
        _channel(db, "The Show", "series", source_id="s1")
        ep = _episode(db, "s1", 2, ago_min=1)
        with db.session_scope() as session:
            RepositoryFactory(session).episodes.record_watch_progress(ep, 540, 2640)
        with db.session_scope() as session:
            RepositoryFactory(session).episodes.mark_watched_bulk([ep], False)
        assert "The Show" not in _history(db)
