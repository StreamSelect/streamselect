"""Sports: "Listings from 4:01 PM" and a Refresh, under the sort row (owner, 2026-11-20).

The view gave no hint how old its listings were, so a night with the network down
and a source posting late looked like a stuck view. Asserted on what is drawn (the
line sits below the sort row, at its right) and on what Refresh queues.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest

from streamselect.core.repositories import RepositoryFactory
from streamselect.core.time_display import clock_text
from streamselect.gui.sports_freshness import listings_text
from streamselect.core.games.store import refresh_games
from tests.test_game_finder import _seed_db
from tests.test_sports_view import NOW, _settle, _view


@pytest.fixture
def games_db(db):
    _seed_db(db)
    refresh_games(db, NOW)
    return db


def test_the_words():
    now = datetime(2026, 11, 21, 18, 30)
    four = datetime(2026, 11, 21, 16, 1)
    assert listings_text(four, now=now) == f"Listings from {clock_text(four)}"
    yesterday = four - timedelta(days=1)
    assert listings_text(yesterday, now=now) == f"Listings from Fri {clock_text(yesterday)}"
    assert listings_text(four, failed=True, now=now) == f"Refresh failed · listings from {clock_text(four)}"
    assert listings_text(None) == "Listings not refreshed yet"
    assert listings_text(four, refreshing=True) == "Refreshing listings…"


def test_the_line_sits_under_the_sort_row_at_its_right_and_refresh_asks(games_db, qapp, owned_widgets):
    view = _view(games_db, qapp, owned_widgets, NOW)
    when = datetime(2026, 11, 21, 16, 1)
    view.set_listings(when)
    _settle(qapp)
    label, toolbar = view.listings_label, view.toolbar
    assert label.text().startswith("Listings from ")
    top = label.mapTo(view, QPoint(0, 0)).y()
    assert top >= toolbar.mapTo(view, QPoint(0, toolbar.height())).y(), "below the sort row"
    right = view.listings_refresh.mapTo(view, QPoint(view.listings_refresh.width(), 0)).x()
    sort_right = toolbar.mapTo(view, QPoint(toolbar.width(), 0)).x()
    assert abs(right - sort_right) <= 2, "right-aligned with the sort row"
    asked = []
    view.listingsRefreshRequested.connect(lambda: asked.append(True))
    QTest.mouseClick(view.listings_refresh, Qt.MouseButton.LeftButton)
    assert asked == [True]
    view.set_listings(when, failed=True)
    assert view.listings_label.text().startswith("Refresh failed")


def _host(db, view):
    from streamselect.gui.catalog_refresh_tick import _CatalogRefreshTickMixin
    from streamselect.gui.main_window_sports import _SportsViewMixin

    class Host(_SportsViewMixin, _CatalogRefreshTickMixin):
        pass

    host = Host()
    host.sports_view = view
    host.refresh_queue_manager = MagicMock()
    host.refresh_queue_manager.is_queued_or_running.side_effect = (
        lambda pid: any(c.args[0] == pid for c in host.refresh_queue_manager.enqueue.call_args_list))

    def run_query(fn, on_result, *, token_ref=None, on_error=None, commit=False):
        with db.session_scope(commit=commit) as s:
            on_result(fn(RepositoryFactory(s)))

    host._run_query = run_query
    return host


def test_refresh_queues_a_live_only_refresh_of_each_active_source(games_db, qapp, owned_widgets):
    view = _view(games_db, qapp, owned_widgets, NOW)
    host = _host(games_db, view)
    host._refresh_sports_listings()
    queued = {(c.args[0], c.kwargs.get("kind")) for c in host.refresh_queue_manager.enqueue.call_args_list}
    assert queued == {("p1", "live_only"), ("p2", "live_only")}, "active sources only, live lane"
    assert view.listings_label.text() == "Refreshing listings…"


def test_when_the_batch_ends_the_line_shows_the_oldest_time_or_the_failure(games_db, qapp, owned_widgets):
    with games_db.session_scope() as s:
        repos = RepositoryFactory(s)
        repos.providers.mark_live_refreshed("p1", when=datetime(2026, 11, 21, 16, 1))
        repos.providers.mark_live_refreshed("p2", when=datetime(2026, 11, 21, 18, 12))
    view = _view(games_db, qapp, owned_widgets, NOW)
    host = _host(games_db, view)
    host._note_sports_source_refreshed("p2", False, "timed out", None)
    host._show_sports_listings_time()
    assert view.listings_label.text().startswith("Refresh failed")
    host._show_sports_listings_time()                 # the next batch went fine
    oldest = datetime(2026, 11, 21, 16, 1)
    assert view.listings_label.text() == listings_text(oldest), "the oldest source's time"
