"""Regression: the unnamed-guide re-fetch must persist its "attempted" marker across
launches, not just within one session.

Background (sibling of an earlier change): a time-fresh provider whose guide rows are unmatched AND
unnamed triggers a ONE-TIME re-fetch to populate ``channel_name`` so the cheap DB-only
relink can then work.  an earlier change guarded that with the in-memory ``_unmatched_refresh_attempted``
set — which RESETS every launch.  A feed that genuinely serves nameless programme rows
(a ``channel_epg_id`` with no ``<channel>`` display-name in the XMLTV → stored with an
empty ``channel_name`` that no re-fetch can fill, e.g. Delta) keeps
``has_unmatched_unnamed_epg`` permanently True, so the branch fired the FULL-guide
re-fetch on EVERY launch, ignoring ``epg_refresh_interval``.

Fix: a persistent ``ProviderDB.epg_unnamed_refetch_attempted`` marker (set + committed
when the branch fires) stops the cross-launch loop.  A content refresh no longer
clears it (it re-armed the re-fetch every launch); the refresh's own EPG fetch is the
retry.  The normal
``needs_refresh`` interval still governs periodic refreshes.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch


from streamselect.core.database import ProviderDB, EpgProgramDB
from streamselect.core.epg_manager import EpgManager
from streamselect.core.epg_utils import now_utc
from streamselect.core.provider_loader import ProviderLoadThread


def _make_manager(db):
    config = MagicMock()
    config.epg_auto_refresh = True
    config.epg_default_refresh_interval = "auto"
    return EpgManager(db, config, notifications=None)


def _add_provider(session, pid, *, last_fetched_offset=timedelta(0),
                  marker=False):
    """A time-FRESH provider (needs_refresh False under auto) unless the caller ages
    ``last_fetched_offset`` far enough back to elapse the auto delta.

    Guide depth is 2 days (start = -1d, end = +1d) → auto delta = 1 day.

    ``urls`` is populated so ``effective_epg_url`` (derives from credentials +
    urls, never the cached ``epg_url`` column) resolves non-empty.
    """
    now = now_utc()
    session.add(ProviderDB(
        id=pid, name=pid, type="xtream", url="http://e.com", username="u", password="p",
        urls=[{"url": "http://e.com", "priority": 0}],
        is_active=True, epg_url="http://e/xmltv.php", epg_enabled=True,
        epg_last_fetched=now - last_fetched_offset,
        epg_data_start=now - timedelta(days=1),
        epg_data_end=now + timedelta(days=1),
        epg_refresh_interval="auto",
        epg_unnamed_refetch_attempted=marker,
    ))


def _add_epg_row(session, pid, *, channel_name, channel_db_id=None):
    """An EPG row; ``channel_name=""`` + ``channel_db_id=None`` is the unnamed/unmatched
    legacy case that keeps ``has_unmatched_unnamed_epg`` True.

    It starts in an hour, so it actually backs the provider's ``epg_data_end``
    of +1 day: the refresh floor now asks whether anything still STARTS (ledger
    F8), and a "time-fresh" guide whose only programme has already begun is an
    exhausted one.
    """
    now = now_utc()
    session.add(EpgProgramDB(
        provider_id=pid, channel_epg_id="x.tv", channel_db_id=channel_db_id,
        channel_name=channel_name, title="Show",
        start_time=now + timedelta(hours=1), stop_time=now + timedelta(hours=2),
    ))


def _read_marker(db, pid) -> bool:
    with db.session_scope(commit=False) as s:
        prov = s.query(ProviderDB).filter_by(id=pid).first()
        return bool(prov.epg_unnamed_refetch_attempted)


# ---------------------------------------------------------------------------
# The core loop-fix: a persisted marker blocks the every-launch re-fetch.
# ---------------------------------------------------------------------------

def test_persistent_marker_blocks_refetch_across_launch(db):
    """Marker SET + nameless-forever rows + interval NOT elapsed → a FRESH manager
    (empty in-memory guard, i.e. a new app launch) must NOT re-fetch. This is the loop
    the in-memory-only guard failed to stop."""
    with db.session_scope() as s:
        _add_provider(s, "delta", marker=True)          # prior launch already attempted
        _add_epg_row(s, "delta", channel_name="")       # unnamed + unmatched, forever

    manager = _make_manager(db)                          # fresh in-memory set == new launch
    with patch.object(manager, "_start_refresh") as mock_refresh:
        manager.refresh_all_if_needed()
        mock_refresh.assert_not_called()
    manager._executor.shutdown(wait=False)


def test_first_attempt_refetches_once_and_persists_marker(db):
    """Marker UNSET + nameless rows → re-fetch fires exactly once AND the persistent
    marker is committed to the DB (so the next launch is blocked)."""
    with db.session_scope() as s:
        _add_provider(s, "delta", marker=False)
        _add_epg_row(s, "delta", channel_name="")

    assert _read_marker(db, "delta") is False, "precondition: marker starts unset"

    manager = _make_manager(db)
    with patch.object(manager, "_start_refresh") as mock_refresh:
        manager.refresh_all_if_needed()
        assert mock_refresh.call_count == 1, "unnamed guide should re-fetch once"
    manager._executor.shutdown(wait=False)

    assert _read_marker(db, "delta") is True, "marker must persist after the attempt"


def test_marker_persists_stops_next_launch_end_to_end(db):
    """End-to-end: attempt once (marker committed), then a brand-new manager does NOT
    re-fetch — the interval throttle, not the branch, now governs."""
    with db.session_scope() as s:
        _add_provider(s, "delta", marker=False)
        _add_epg_row(s, "delta", channel_name="")

    m1 = _make_manager(db)
    with patch.object(m1, "_start_refresh") as r1:
        m1.refresh_all_if_needed()
        assert r1.call_count == 1
    m1._executor.shutdown(wait=False)

    m2 = _make_manager(db)  # simulates the next app launch
    with patch.object(m2, "_start_refresh") as r2:
        m2.refresh_all_if_needed()
        r2.assert_not_called()
    m2._executor.shutdown(wait=False)


# ---------------------------------------------------------------------------
# A content refresh no longer re-arms the marker: it re-armed it on every
# scheduled 3-hourly live refresh, so a feed serving nameless rows got its
# "one-time" re-fetch at every launch. The refresh's own EPG fetch is the retry.
# ---------------------------------------------------------------------------

def test_content_refresh_does_not_rearm_the_refetch(db):
    with db.session_scope() as s:
        _add_provider(s, "delta", marker=True)
        _add_epg_row(s, "delta", channel_name="")
    assert not hasattr(ProviderLoadThread, "_reset_epg_unnamed_refetch_marker")
    manager = _make_manager(db)
    with patch.object(manager, "_start_refresh") as mock_refresh:
        manager.refresh_all_if_needed()
        mock_refresh.assert_not_called()
    manager._executor.shutdown(wait=False)


# ---------------------------------------------------------------------------
# The intended an earlier change convergence still holds: a feed whose names DO populate stops
# on its own (the DB condition clears) — independent of the marker.
# ---------------------------------------------------------------------------

def test_populated_names_converge_and_stop(db):
    """A converging feed whose re-fetch DID populate names stops even after the marker
    is cleared: ``has_unmatched_unnamed_epg`` is False, so the branch never fires."""
    with db.session_scope() as s:
        _add_provider(s, "good", marker=True)
        # Re-fetch populated the name (and matched it) — the converging case.
        _add_epg_row(s, "good", channel_name="Good Channel 1", channel_db_id=None)

    manager = _make_manager(db)
    with patch.object(manager, "_start_refresh") as mock_refresh:
        manager.refresh_all_if_needed()
        mock_refresh.assert_not_called()
    manager._executor.shutdown(wait=False)


# ---------------------------------------------------------------------------
# The normal interval throttle is unchanged by the marker.
# ---------------------------------------------------------------------------

def test_interval_elapsed_still_refreshes_despite_marker(db):
    """The persistent marker only gates the unnamed-legacy branch; when the normal
    interval has elapsed, ``needs_refresh`` fires the refresh regardless of the marker."""
    with db.session_scope() as s:
        # auto delta = half of 2-day depth = 1 day; last fetch 2 days ago → elapsed.
        _add_provider(s, "delta", last_fetched_offset=timedelta(days=2), marker=True)
        _add_epg_row(s, "delta", channel_name="")

    manager = _make_manager(db)
    with patch.object(manager, "_start_refresh") as mock_refresh:
        manager.refresh_all_if_needed()
        assert mock_refresh.call_count == 1, "interval elapsed → normal refresh still fires"
    manager._executor.shutdown(wait=False)


def test_interval_not_elapsed_and_no_unnamed_rows_no_refresh(db):
    """Interval not elapsed + no nameless rows + marker unset → nothing refreshes
    (baseline: the marker change didn't perturb the quiet path)."""
    with db.session_scope() as s:
        _add_provider(s, "delta", marker=False)
        _add_epg_row(s, "delta", channel_name="Named", channel_db_id="c1")  # matched

    manager = _make_manager(db)
    with patch.object(manager, "_start_refresh") as mock_refresh:
        manager.refresh_all_if_needed()
        mock_refresh.assert_not_called()
    manager._executor.shutdown(wait=False)
