"""Waiting out a source's connection limit, then starting the title (Source Analytics Q7).

A 458/509 while StreamSelect holds nothing from the source is a stream the source is
still counting. The wait checks the account endpoint, starts the title when a
connection frees, records how long that took, and the Analytics tab reports it.
Real ``Database`` on a ``tmp_path`` file; the account check is a fake thread that
answers at once, so the real ``poll`` → ``on_checked`` path runs.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QObject, pyqtSignal

from streamselect.core.database import Database, ProviderDB
from streamselect.core.playback_models import ConnectionHoldDB
from streamselect.core.repositories import RepositoryFactory
from streamselect.gui import connection_wait
from streamselect.gui import playback_start_watch as watch
from streamselect.gui.playback_start_watch import FAILED_AFTER_TICKS, PlayAttempt

ATTEMPT = PlayAttempt("ch-1", "Futurama S01E01", "http://x/1.ts", provider_id="delta")


@pytest.fixture()
def db(tmp_path):
    d = Database(f"sqlite:///{tmp_path / 'test.db'}")
    d.create_tables()
    with d.session_scope() as s:
        s.add(ProviderDB(id="delta", name="Delta", type="xtream", url="http://t", username="u",
                         password="p", max_connections=1, account_active_cons=1))
    yield d
    d.close()


def _host(db, *, ours=()):
    def run_query(fn, on_result, commit=False, on_error=None, **_kw):
        with db.session_scope() as s:
            on_result(fn(RepositoryFactory(s)))
    host = SimpleNamespace(db=db, notification_manager=MagicMock(), status=MagicMock(),
                           play_channel_by_id=MagicMock(), _run_query=run_query,
                           stream_retry_manager=MagicMock(),
                           _provider_display_name=lambda pid: "Delta")
    host.notification_manager.show.return_value = "notif-wait"
    host.player_manager = MagicMock()
    host.player_manager.resolve_key.return_value = "delta-key"
    host.player_manager.connection_accountant.holders.return_value = [
        SimpleNamespace(holder_id=h) for h in ours]
    return host


class _FakeAccountThread(QObject):
    """Stands in for FetchAccountInfoThread: answers on start() with the next reply."""
    finished = pyqtSignal(bool, object)
    replies: list = []

    def __init__(self, provider):
        super().__init__()

    def start(self):
        self.finished.emit(True, _FakeAccountThread.replies.pop(0))

    def wait(self, _ms):
        return True


@pytest.fixture()
def fake_account(monkeypatch):
    monkeypatch.setattr("streamselect.gui.provider_editor_workers.FetchAccountInfoThread", _FakeAccountThread)
    return _FakeAccountThread.replies


def _refuse(host):
    with patch("streamselect.gui.playback_start_watch._http_refusal", return_value=509):
        watch.arm(host, ATTEMPT)
        for _ in range(FAILED_AFTER_TICKS):
            watch.on_idle_tick(host)


def test_a_refusal_starts_a_wait_instead_of_the_failure_toast(qapp, db):
    host = _host(db)
    _refuse(host)
    wait = host._connection_wait
    titles = [c.kwargs["title"] for c in host.notification_manager.show.call_args_list]
    assert titles == ["Waiting for a connection on Delta"], "no 'Stream did not start' alongside"
    kwargs = host.notification_manager.show.call_args.kwargs
    assert kwargs["dismissible"] is False and kwargs["actions"][0][0] == "Cancel"
    assert wait.timer.isActive() and wait.timer.interval() == 30_000
    host.stream_retry_manager.add_failure.assert_not_called()
    connection_wait.cancel(host)


def test_when_streamselect_itself_holds_the_source_it_does_not_wait(qapp, db):
    host = _host(db, ours=["delta-other-window"])
    _refuse(host)
    assert "_connection_wait" not in host.__dict__
    assert host.notification_manager.show.call_args.kwargs["title"] == "Stream did not start"


def test_a_freed_connection_starts_the_title_and_records_the_hold(qapp, db, fake_account):
    host = _host(db)
    _refuse(host)
    wait = host._connection_wait
    wait.refused_at -= timedelta(minutes=22)
    fake_account[:] = [{"active_cons": 1, "max_connections": 1}]
    wait.poll()                                    # still full: keeps waiting
    host.play_channel_by_id.assert_not_called()
    assert host._connection_wait is wait
    fake_account[:] = [{"active_cons": 0, "max_connections": 1}]
    wait.poll()
    host.play_channel_by_id.assert_called_once_with("ch-1")
    host.notification_manager.dismiss.assert_called_with("notif-wait")
    assert "_connection_wait" not in host.__dict__
    with db.session_scope(commit=False) as s:
        [hold] = s.query(ConnectionHoldDB).all()
        assert (hold.provider_id, 22 * 60 <= hold.seconds < 23 * 60) == ("delta", True)
    assert "22 min" in host.status.call_args.args[0]


def test_cancel_stops_the_wait_and_a_late_answer_is_ignored(qapp, db, fake_account):
    host = _host(db)
    _refuse(host)
    wait = host._connection_wait
    cancel_cb = host.notification_manager.show.call_args.kwargs["actions"][0][1]
    cancel_cb()
    assert not wait.timer.isActive() and "_connection_wait" not in host.__dict__
    wait.on_checked(True, {"active_cons": 0, "max_connections": 1})
    host.play_channel_by_id.assert_not_called()


def test_starting_another_play_cancels_the_wait(qapp, db):
    host = _host(db)
    _refuse(host)
    wait = host._connection_wait
    watch.arm(host, PlayAttempt("ch-2", "Something else", "http://x/2.ts", provider_id="delta"))
    assert not wait.timer.isActive() and "_connection_wait" not in host.__dict__


def test_it_gives_up_after_an_hour(qapp, db, fake_account):
    host = _host(db)
    _refuse(host)
    wait = host._connection_wait
    wait.started -= connection_wait.GIVE_UP_AFTER_S + 1
    wait.poll()
    assert "_connection_wait" not in host.__dict__
    assert host.notification_manager.show.call_args.kwargs["title"] == "Stopped waiting for a connection"
    host.play_channel_by_id.assert_not_called()


def test_connections_summary_and_provider_delete(db):
    now = datetime(2026, 10, 31, 20, 0)
    with db.session_scope() as s:
        repo = RepositoryFactory(s).playback_events
        for secs in (600, 1320, 1500):
            repo.record_hold("delta", now, secs)
    with db.session_scope(commit=False) as s:
        c = RepositoryFactory(s).playback_events.connections("delta")
    assert (c.limit, c.in_use, c.waits, c.median_seconds, c.longest_seconds) == (1, 1, 3, 1320, 1500)
    with db.session_scope() as s:
        RepositoryFactory(s).playback_events.delete_for_provider("delta")
    with db.session_scope(commit=False) as s:
        assert s.query(ConnectionHoldDB).count() == 0


# ── a hold is measured from our stream's end, across Play pressed again ──────

def _hold_row(db):
    with db.session_scope(commit=False) as s:
        [hold] = s.query(ConnectionHoldDB).all()
        return SimpleNamespace(**{c: getattr(hold, c) for c in
                                  ("refused_at", "seconds", "ended_at", "freed_at", "checks", "plays")})


def test_pressing_play_again_mid_hold_continues_it_from_our_streams_end(qapp, db, fake_account):
    host = _host(db)
    connection_wait.note_stream_ended(host, "delta")
    host._source_stream_ended["delta"] -= timedelta(minutes=16)
    _refuse(host)
    first = host._connection_wait
    first.refused_at -= timedelta(minutes=15)
    fake_account[:] = [{"active_cons": 1, "max_connections": 1}]
    first.poll()
    _refuse(host)                                  # the user presses Play again: refused again
    second = host._connection_wait
    assert second is not first and second.ledger is first.ledger, "one hold, not a new one"
    fake_account[:] = [{"active_cons": 0, "max_connections": 1}]
    second.poll()
    hold = _hold_row(db)
    assert hold.plays == 2 and hold.checks == 2
    assert 15 * 60 <= hold.seconds < 16 * 60, "from the FIRST refusal, not the last"
    assert 16 * 60 <= (hold.freed_at - hold.ended_at).total_seconds() < 17 * 60


def test_a_play_that_starts_on_its_own_closes_the_hold(qapp, db):
    host = _host(db)
    connection_wait.note_stream_ended(host, "delta")
    _refuse(host)
    connection_wait.cancel(host)                   # what arm() does for the next play
    connection_wait.note_started(host, "delta")
    hold = _hold_row(db)
    assert hold.plays == 1 and hold.checks == 0 and hold.ended_at is not None
    connection_wait.note_started(host, "delta")    # recorded once
    with db.session_scope(commit=False) as s:
        assert s.query(ConnectionHoldDB).count() == 1


def test_an_old_cancelled_hold_is_not_continued(qapp, db):
    host = _host(db)
    _refuse(host)
    first = host._connection_wait.ledger
    connection_wait.cancel(host)
    first.cancelled_at -= connection_wait.CARRY_S + 1
    _refuse(host)
    assert host._connection_wait.ledger is not first
    connection_wait.cancel(host)


def test_with_past_holds_the_first_check_waits_for_the_usual_free_up(qapp, db):
    with db.session_scope() as s:
        repo = RepositoryFactory(s).playback_events
        t = datetime(2026, 11, 1, 20, 0)
        for secs in (500, 600, 700):
            repo.record_hold("delta", t, 30, ended_at=t, freed_at=t + timedelta(seconds=secs))
    host = _host(db)
    connection_wait.note_stream_ended(host, "delta")
    host._source_stream_ended["delta"] -= timedelta(seconds=40)
    _refuse(host)
    wait = host._connection_wait
    assert 495_000 <= wait.timer.interval() <= 500_000, "600 s usual − 60 s early − 40 s already gone"
    assert "usually frees one 10 min after a stream ends" in \
        host.notification_manager.show.call_args.kwargs["message"]
    connection_wait.cancel(host)


def test_first_check_timing():
    now = datetime(2026, 11, 16, 21, 0)
    assert connection_wait.first_check_ms(None, None, now) == connection_wait.POLL_MS
    assert connection_wait.first_check_ms(600, now - timedelta(minutes=20), now) == connection_wait.POLL_MS
    assert connection_wait.first_check_ms(600, None, now) == 540_000


def test_a_streams_end_is_noted_once_not_moved_by_the_next_play(qapp, db):
    host = _host(db)
    host._run_query = lambda *a, **k: None
    watch.arm(host, ATTEMPT)
    host._health_ever_progressed = True
    watch.on_player_gone(host, "Quit")
    ended = host._source_stream_ended["delta"]
    host._source_stream_ended["delta"] = ended - timedelta(minutes=3)
    watch.arm(host, ATTEMPT)                       # Play pressed three minutes later
    assert host._source_stream_ended["delta"] == ended - timedelta(minutes=3)
