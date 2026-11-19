"""The game finder runs once at launch, not twice back to back."""

from __future__ import annotations

import threading
from unittest import mock

from streamselect.gui import game_tracker as gt


def test_the_launch_timer_does_not_queue_a_second_run_behind_one_in_flight(qapp):
    release, calls = threading.Event(), []

    def slow_refresh(_db, **_kw):
        calls.append(1)
        release.wait(5)
        return {}

    with mock.patch.object(gt, "refresh_games", slow_refresh):
        tracker = gt.GameTracker(db=None)
        try:
            tracker.request()                 # the Sports view, open at launch
            tracker.request_first()           # the launch timer fires mid-run
            release.set()
            tracker._pool.shutdown(wait=True)
            assert len(calls) == 1
            assert tracker.has_run and not tracker.busy
        finally:
            tracker.shutdown()


def test_the_launch_run_happens_when_nothing_ran_and_not_again_after(qapp):
    calls = []
    with mock.patch.object(gt, "refresh_games", lambda _db, **_kw: calls.append(1) or {}):
        tracker = gt.GameTracker(db=None)
        try:
            tracker.request_first()
            tracker._pool.submit(lambda: None).result(5)
            tracker.request_first()
            tracker._pool.shutdown(wait=True)
            assert len(calls) == 1
        finally:
            tracker.shutdown()


def test_a_real_change_still_runs_again_after_a_run_in_flight(qapp):
    release, calls = threading.Event(), []

    def slow_refresh(_db, **_kw):
        calls.append(1)
        release.wait(5)
        return {}

    with mock.patch.object(gt, "refresh_games", slow_refresh):
        tracker = gt.GameTracker(db=None)
        try:
            tracker.request()
            tracker.request()                 # a refresh finished meanwhile
            release.set()
            tracker._pool.shutdown(wait=True)
            assert len(calls) == 2
        finally:
            tracker.shutdown()


def test_a_run_that_finishes_after_shutdown_tells_nobody(qapp):
    """The run in flight when the window closes must not emit games_updated: its
    listeners (the alert notifier) run queries on a pool that is gone (v1.0.9 tag run)."""
    release, emitted = threading.Event(), []

    def slow_refresh(_db, **_kw):
        release.wait(5)
        return {"hockey/NHL": 1}

    with mock.patch.object(gt, "refresh_games", slow_refresh):
        tracker = gt.GameTracker(db=None)
        tracker.games_updated.connect(emitted.append)
        tracker.request()
        tracker.shutdown()                 # the window closes mid-run
        release.set()
        pool = tracker._pool
        pool.shutdown(wait=True)
        qapp.processEvents()
        assert emitted == []


def test_a_run_that_fails_because_the_database_closed_says_nothing(qapp):
    release, emitted = threading.Event(), []

    def failing_refresh(_db, **_kw):
        release.wait(5)
        raise RuntimeError("database closed")

    with mock.patch.object(gt, "refresh_games", failing_refresh):
        tracker = gt.GameTracker(db=None)
        tracker.games_updated.connect(emitted.append)
        tracker.request()
        tracker.shutdown()
        release.set()
        tracker._pool.shutdown(wait=True)
        qapp.processEvents()
        assert emitted == []
