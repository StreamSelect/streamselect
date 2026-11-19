"""EPG refresh timed by what lies AHEAD (owner, 2026-11-18: the guide ran out every
day before Auto refreshed; "it knows when it runs out").

Measured on the owner's data: the source serves ~24 h of programme starts ahead and
the app keeps 24 h of past programmes, so the old half-of-depth Auto waited ~30 h.
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

from streamselect.core.database import ProviderDB
from streamselect.core.epg_manager import EpgManager
from streamselect.core.epg_utils import (
    epg_auto_delta, epg_auto_refresh_delta, epg_runs_out_soon, guide_freshness, now_utc,
)
from tests.test_epg_auto_refresh import _add_provider


def _manager(db, *, default="auto", margin_min=60):
    config = MagicMock()
    config.epg_auto_refresh = True
    config.epg_default_refresh_interval = default
    config.epg_refresh_before_runout_minutes = margin_min
    return EpgManager(db, config, notifications=None)


def _seed(db, *, fetched_ago, ahead_at_fetch, interval="default"):
    """A guide fetched *fetched_ago* that reached *ahead_at_fetch* past the fetch,
    with 24 h of past programmes kept and long last programmes ending 12 h later."""
    fetched = now_utc() - fetched_ago
    last_start = fetched + ahead_at_fetch
    with db.session_scope() as s:
        _add_provider(s, "p1", epg_last_fetched=fetched, epg_data_start=fetched - timedelta(hours=24),
                      epg_data_end=last_start + timedelta(hours=12), epg_refresh_interval=interval)
        s.get(ProviderDB, "p1").epg_last_start = last_start
    return fetched, last_start


def _provider(db):
    with db.session_scope() as s:
        p = s.get(ProviderDB, "p1")
        s.expunge(p)
        return p


# ── the arithmetic ─────────────────────────────────────────────────────────

def test_auto_is_half_of_what_lies_ahead_not_half_the_stored_depth():
    fetched = now_utc()
    start, end, last = fetched - timedelta(hours=24), fetched + timedelta(hours=36), fetched + timedelta(hours=24)
    assert epg_auto_delta(start, end) == timedelta(hours=30), "the old number: longer than the guide"
    assert epg_auto_refresh_delta(fetched, last, start, end) == timedelta(hours=12)


def test_auto_keeps_its_clamp_and_falls_back_without_a_latest_start():
    f = now_utc()
    assert epg_auto_refresh_delta(f, f + timedelta(hours=4), None, None) == timedelta(hours=6), "floor"
    assert epg_auto_refresh_delta(f, f + timedelta(days=30), None, None) == timedelta(days=7), "ceiling"
    s, e = f - timedelta(days=1), f + timedelta(days=3)
    assert epg_auto_refresh_delta(f, None, s, e) == epg_auto_delta(s, e), "older guides: as before"
    assert epg_auto_refresh_delta(f, f - timedelta(hours=1), s, e) == epg_auto_delta(s, e), "stale at source"


def test_runs_out_soon_opens_its_window_once():
    f, margin = now_utc() - timedelta(hours=23, minutes=30), timedelta(hours=1)
    last = f + timedelta(hours=24)                       # 30 min from now
    assert epg_runs_out_soon(f, last, margin)
    assert not epg_runs_out_soon(f, last, margin, now=f + timedelta(hours=22)), "too early"
    refetched = now_utc() - timedelta(minutes=10)        # fetched INSIDE the window, nothing newer came
    assert not epg_runs_out_soon(refetched, last, margin), "no re-fetch loop"
    assert not epg_runs_out_soon(f, f - timedelta(hours=1), margin), "stale at source: not this rule"


# ── needs_refresh ──────────────────────────────────────────────────────────

def test_auto_refreshes_after_12h_for_a_guide_reaching_24h_ahead(db):
    _seed(db, fetched_ago=timedelta(hours=13), ahead_at_fetch=timedelta(hours=24))
    assert _manager(db).needs_refresh(_provider(db))


def test_auto_waits_before_half_of_what_lies_ahead(db):
    _seed(db, fetched_ago=timedelta(hours=11), ahead_at_fetch=timedelta(hours=24))
    assert not _manager(db).needs_refresh(_provider(db))


def test_a_fixed_daily_interval_still_refreshes_before_the_guide_runs_out(db):
    _seed(db, fetched_ago=timedelta(hours=23, minutes=30), ahead_at_fetch=timedelta(hours=24),
          interval="1d")
    assert _manager(db, default="1d").needs_refresh(_provider(db)), "30 min left, inside the 60 min margin"
    assert not _manager(db, default="1d", margin_min=15).needs_refresh(_provider(db)), "the margin is the setting's"


def test_a_fetch_inside_the_window_that_brought_nothing_newer_is_not_repeated(db):
    fetched, last = _seed(db, fetched_ago=timedelta(minutes=10), ahead_at_fetch=timedelta(minutes=40),
                          interval="1d")
    assert not _manager(db, default="1d").needs_refresh(_provider(db))


# ── the timer and the freshness line ───────────────────────────────────────

def test_the_run_out_timer_is_set_for_shortly_before_the_last_start(db, qapp):
    _fetched, last = _seed(db, fetched_ago=timedelta(hours=2), ahead_at_fetch=timedelta(hours=24))
    mgr = _manager(db)
    try:
        mgr.start_scheduler()
        due = mgr.runout_due_at()
        assert abs(due - (last - timedelta(hours=1))) < timedelta(seconds=1)
        assert mgr._runout_timer.isActive()
        left = mgr._runout_timer.remainingTime() / 1000
        assert abs(left - (due - now_utc()).total_seconds()) < 5
    finally:
        mgr.stop_scheduler()


def test_the_freshness_line_states_the_interval_the_scheduler_uses():
    f = now_utc() - timedelta(hours=1)
    fresh = guide_freshness("http://e/xmltv.php", f + timedelta(hours=36),
                            epg_data_start=f - timedelta(hours=24),
                            last_fetched=f, last_start=f + timedelta(hours=24))
    assert "reaches ~24h ahead" in fresh.text and "every 12h" in fresh.text, fresh.text
