"""Clear History can also scrub the play record behind source analytics.

Source analytics stopped reading History (a cleared History had emptied it), so
the play record became a second list of everything watched that Clear History
left behind. The dialog offers an unticked box to forget it too: titles and
time watched go; each play's outcome stays, because Playback's reliability
figures describe the source, not the viewer.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QMessageBox, QWidget

from streamselect.core.database import ChannelDB, Database, ProviderDB
from streamselect.core.repositories import RepositoryFactory
from streamselect.gui.main_window_history import _HistoryMixin
from tests.conftest import destroy_widget, wire_status_method

PID = "p"


@pytest.fixture()
def db(tmp_path):
    d = Database(f"sqlite:///{tmp_path / 'scrub.db'}")
    d.create_tables()
    with d.session_scope() as s:
        s.add(ProviderDB(id=PID, name="P", type="xtream", url="http://example.com", is_active=True))
        s.add(ChannelDB(id="c1", source_id="1", provider_id=PID, name="A Film", media_type="movie",
                        play_count=2, last_played=datetime.now()))
        repo = RepositoryFactory(s).playback_events
        start = datetime.utcnow() - timedelta(hours=3)
        for n, outcome in enumerate(("started", "started", "refused")):
            event = repo.record(provider_id=PID, channel_id="c1", title="A Film", outcome=outcome,
                                started_at=start + timedelta(minutes=n), time_to_picture_ms=1500)
            if outcome == "started":
                repo.update(event, seconds_watched=600)
    yield d
    d.close()


class _Host(QWidget, _HistoryMixin):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.status_bar = MagicMock()
        wire_status_method(self)
        self.sidebar_sections = {}
        self.load_history = MagicMock()
        self.load_favorites = MagicMock()


def _answer(monkeypatch, *, tick: bool, seen: list):
    def exec_(box):
        check = box.checkBox()
        seen.append((check.text(), check.isChecked()))
        if tick:
            box.checkBox().setChecked(True)
        return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, "exec", exec_)


def _clear(qapp, db, monkeypatch, *, tick):
    seen: list = []
    _answer(monkeypatch, tick=tick, seen=seen)
    host = _Host(db)
    try:
        host.clear_history()
    finally:
        destroy_widget(host)
    return seen


def test_the_box_is_offered_unticked(qapp, db, monkeypatch):
    seen = _clear(qapp, db, monkeypatch, tick=False)
    text, ticked = seen[0]
    assert "source analytics" in text and not ticked


def test_unticked_leaves_the_play_record(qapp, db, monkeypatch):
    _clear(qapp, db, monkeypatch, tick=False)
    with db.session_scope(commit=False) as s:
        assert s.query(ChannelDB).filter_by(id="c1").one().play_count == 0
        viewing = RepositoryFactory(s).analytics.viewing(PID)
    assert viewing.plays == 2 and viewing.top[0][0] == "A Film"


def test_ticked_forgets_titles_and_time_but_keeps_reliability(qapp, db, monkeypatch):
    _clear(qapp, db, monkeypatch, tick=True)
    with db.session_scope(commit=False) as s:
        from streamselect.core.playback_models import PlaybackEventDB
        rows = s.query(PlaybackEventDB).all()
        assert {(r.channel_id, r.title, r.seconds_watched) for r in rows} == {("", "", None)}
        repos = RepositoryFactory(s)
        viewing = repos.analytics.viewing(PID)
        summary = repos.playback_events.summary(PID)
    assert viewing.plays == 0 and viewing.top == () and viewing.seconds_watched == 0
    assert summary.attempts == 3 and summary.started == 2
