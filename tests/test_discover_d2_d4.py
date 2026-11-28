"""Behavioral tests for Discover-view improvement D2.

D2 — Collapsed strips are buffered during streaming load; batch-built afterwards
     to eliminate the "counting up" stutter. (D4, re-collapsed shelves jumping to
     the top of the collapsed zone, went with the zone layout: a collapsed shelf
     now stays at its place in its group — tests/test_discover_dashboard_groups.py.)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _make_card(i: int):
    from streamselect.core.discovery_engine import ContentCard
    return ContentCard(
        channel_id=f"ch-{i}",
        title=f"Movie {i}",
        media_type="movie",
        thumbnail_url=None,
        rating=7.5,
        year=2020,
        genre="Test",
    )


def _make_image_cache():
    ic = MagicMock()
    ic.get_image_async = MagicMock()
    return ic


def _make_shelf_data(key: str, title: str, *, header_only: bool = False):
    """Return a minimal _ShelfData for testing."""
    from streamselect.gui.discover_workers import _ShelfData
    return _ShelfData(
        title=title,
        shelf_key=key,
        cards=[],
        header_only=header_only,
    )


@pytest.fixture()
def make_view(qapp, owned_widgets, tmp_path):
    """The real DiscoverView on a stub DB and image cache; nothing loads until activated."""
    from streamselect.core.config import Config
    from streamselect.gui.discover_view import DiscoverView

    def make():
        cfg = Config(config_dir=tmp_path)
        return owned_widgets.own(DiscoverView(MagicMock(), cfg, _make_image_cache())), cfg
    return make


def _genre_rows(view):
    from streamselect.gui.discover_groups import GENRES
    return view._groups[GENRES]


# ---------------------------------------------------------------------------
# D2 — collapsed-strip buffering
# ---------------------------------------------------------------------------

class TestCollapsedStripBuffering:
    """D2: header_only shelves are buffered; batch-built in one pass."""

    def test_header_only_shelves_buffered_not_built_immediately(self, make_view):
        """header_only _ShelfData must land in _pending_collapsed, not in its group yet."""
        view, cfg = make_view()

        # Feed several collapsed strips.
        keys = ["genre:Drama", "genre:Horror", "genre:Action"]
        for key in keys:
            data = _make_shelf_data(key, key.split(":")[1], header_only=True)
            view._on_shelf_ready(data)

        assert _genre_rows(view).count() == 0, (
            "the Genres group must be empty while strips are still buffered — "
            f"got {_genre_rows(view).count()} widgets"
        )
        assert len(view._pending_collapsed) == len(keys), (
            f"all {len(keys)} header_only shelves must be in _pending_collapsed, "
            f"got {len(view._pending_collapsed)}"
        )
        # No widgets built yet.
        for key in keys:
            assert key not in view._shelf_widgets, (
                f"shelf widget for {key!r} must not exist before batch flush"
            )

    def test_more_btn_count_reflects_pending_total(self, make_view):
        """More Categories count includes both built and pending collapsed strips."""

        view, cfg = make_view()

        # Add one already-built collapsed strip.
        view._on_shelf_ready(_make_shelf_data("genre:A", "A", header_only=True))
        view._flush_pending_collapsed()

        # Buffer two pending strips.
        for key in ["genre:Drama", "genre:Horror"]:
            view._pending_collapsed.append(
                _make_shelf_data(key, key.split(":")[1], header_only=True)
            )
        view._update_group_heads()

        btn_text = _genre_rows(view).heading.text()
        assert btn_text.endswith("(3)"), (
            f"the Genres heading must show the total count (built + pending = 3), "
            f"got: {btn_text!r}"
        )

    def test_flush_builds_all_pending_strips(self, make_view):
        """After _flush_pending_collapsed, all strips exist and pending is empty."""
        view, cfg = make_view()

        keys = ["genre:Drama", "genre:Horror", "genre:Action", "decade:1990"]
        for key in keys:
            data = _make_shelf_data(key, key.split(":")[-1], header_only=True)
            view._pending_collapsed.append(data)

        # Directly invoke the batch builder (replaces "timer fires").
        view._flush_pending_collapsed()

        assert view._pending_collapsed == [], (
            "_pending_collapsed must be empty after flush"
        )
        assert _genre_rows(view).count() == len(keys) - 1, (
            f"all {len(keys) - 1} genre strips must be in the Genres group after flush, "
            f"got {_genre_rows(view).count()}"
        )
        for key in keys:
            assert key in view._shelf_widgets, (
                f"shelf widget for {key!r} must exist in _shelf_widgets after flush"
            )
            assert key in view._shelf_zones, (
                f"shelf zone for {key!r} must be recorded in _shelf_zones after flush"
            )

    def test_non_header_only_shelf_builds_immediately(self, make_view):
        """A non-collapsed shelf (with cards) still builds immediately — not buffered."""
        from streamselect.gui.discover_workers import _ShelfData

        view, cfg = make_view()

        data = _ShelfData(
            title="Recently Added",
            shelf_key="recently_added",
            cards=[_make_card(0), _make_card(1)],
            header_only=False,
        )
        view._on_shelf_ready(data)

        assert "recently_added" in view._shelf_widgets, (
            "non-header_only shelf must be built immediately (not buffered)"
        )
        assert view._pending_collapsed == [], (
            "non-header_only shelf must not enter the pending buffer"
        )

    def test_flush_is_idempotent_when_called_twice(self, make_view):
        """Calling _flush_pending_collapsed twice does not duplicate widgets."""
        view, cfg = make_view()

        for key in ["genre:Drama", "genre:Horror"]:
            view._pending_collapsed.append(
                _make_shelf_data(key, key.split(":")[1], header_only=True)
            )

        view._flush_pending_collapsed()
        count_after_first = _genre_rows(view).count()

        # Second flush — pending is already empty, should be a no-op.
        view._flush_pending_collapsed()
        count_after_second = _genre_rows(view).count()

        assert count_after_first == count_after_second == 2, (
            "second flush must not add duplicate widgets; "
            f"got {count_after_first} after first flush, {count_after_second} after second"
        )

    def test_pending_hide_removes_from_buffer_without_flush(self, make_view):
        """Hiding a pending shelf removes it from the buffer, not via full flush."""
        view, cfg = make_view()

        keys = ["genre:Drama", "genre:Horror", "genre:Action"]
        for key in keys:
            view._pending_collapsed.append(
                _make_shelf_data(key, key.split(":")[1], header_only=True)
            )

        # Hide the middle one while still pending.
        view._on_hide_requested("genre:Horror")

        remaining_keys = [d.shelf_key for d in view._pending_collapsed]
        assert "genre:Horror" not in remaining_keys, (
            "hidden shelf must be removed from pending buffer"
        )
        assert len(remaining_keys) == 2, (
            f"two shelves must remain in buffer; got {remaining_keys}"
        )
        # Widget must not have been built for the hidden shelf.
        assert "genre:Horror" not in view._shelf_widgets

    def test_expand_pending_shelf_flushes_batch(self, make_view):
        """Expanding a shelf that's still pending flushes the batch first."""
        view, cfg = make_view()

        keys = ["genre:Drama", "genre:Horror", "genre:Action"]
        for key in keys:
            view._pending_collapsed.append(
                _make_shelf_data(key, key.split(":")[1], header_only=True)
            )

        # Patch _start_expand_fetch so we don't need a real DB.
        view._start_expand_fetch = MagicMock()

        # Expand "genre:Horror" while it's still pending.
        view._on_expand_requested("genre:Horror")

        # All shelves must now be built (flush triggered).
        assert view._pending_collapsed == [], "pending buffer must be empty after expand"
        for key in keys:
            assert key in view._shelf_widgets, (
                f"all shelves must be built after expand-triggered flush; missing {key!r}"
            )

        # The expanded shelf must be in the expanded zone.
        from streamselect.gui.discover_view import _ZONE_EXPANDED
        assert view._shelf_zones.get("genre:Horror") == _ZONE_EXPANDED, (
            "expanded shelf must be in the expanded zone"
        )
