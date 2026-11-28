"""Discover shelf filter — many shelves are unnavigable without one.

The roadmap's proposed fix was to raise ``MIN_COLLECTION_SHELF_MEMBERS``.
Measured against a large library, that does not work: the floor is already
2, and the shelf count barely moves as it rises —

    >= 2 members : 1882 shelves     (today)
    >= 5         : 1848
    >= 10        : 1714
    >= 20        : 1440

There is no long tail to trim. There are genuinely that many collections, so a
cutoff would hide real ones arbitrarily while leaving the surface just as
unusable. Being able to type a name is the fix; a threshold is not.

These tests assert what is actually VISIBLE after filtering — not the contents
of a list, not the order of a dict. A filter that computes the right set and
leaves every widget on screen is the exact failure the UI-test rule exists for.
"""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from streamselect.gui.discover_view import DiscoverView


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def view(qapp, owned_widgets, tmp_path):
    """The real DiscoverView with 4 real shelves fed through the loader's slot.

    Stub DB and image cache: nothing loads until ``on_activate``, so the shelves
    arrive exactly as the loader would send them, in their real groups.
    """
    from unittest.mock import MagicMock

    from streamselect.core.config import Config
    from streamselect.gui.discover_workers import _ShelfData

    cfg = Config(config_dir=tmp_path)
    cfg.discover_zones_seeded = True
    cfg.discover_pinned_shelves = ["decade:1990"]
    cfg.discover_expanded_shelves = ["collection:Apple+ Kids"]
    cfg.discover_more_expanded = True
    v = owned_widgets.own(DiscoverView(MagicMock(), cfg, MagicMock()))
    for key, title in [("collection:Apple+ Kids", "Apple+ Kids"), ("collection:Hindu Subs", "Hindu Subs"),
                       ("genre:Comedy", "Comedy"), ("decade:1990", "1990s")]:
        opens = key in ("decade:1990", "collection:Apple+ Kids")
        v._on_shelf_ready(_ShelfData(title, key, [], header_only=not opens))
    v._flush_pending_collapsed()
    v.show()
    QApplication.processEvents()
    return v


def _visible(view) -> set[str]:
    return {
        s._title for s in view._shelf_widgets.values() if s.isVisible()
    }


class TestFiltering:

    def test_typing_hides_the_shelves_that_do_not_match(self, view):
        view._on_shelf_filter_changed("kids")
        QApplication.processEvents()

        assert _visible(view) == {"Apple+ Kids"}, (
            "non-matching shelves are still on screen — computing the right "
            "set is not the same as rendering it"
        )

    def test_matching_is_case_insensitive(self, view):
        view._on_shelf_filter_changed("APPLE")
        QApplication.processEvents()
        assert _visible(view) == {"Apple+ Kids"}

    def test_it_matches_the_visible_title_not_the_internal_key(self, view):
        """"collection:" is an implementation detail; typing it must not work
        while typing what the user can read must."""
        view._on_shelf_filter_changed("collection")
        QApplication.processEvents()
        assert _visible(view) == set()

        view._on_shelf_filter_changed("Hindu")
        QApplication.processEvents()
        assert _visible(view) == {"Hindu Subs"}

    def test_a_substring_matches_mid_title(self, view):
        view._on_shelf_filter_changed("ubs")
        QApplication.processEvents()
        assert _visible(view) == {"Hindu Subs"}

    def test_it_filters_every_shelf_kind_not_just_collections(self, view):
        """Genre and decade shelves are shelves too — a collection-only filter
        would be a surprise."""
        view._on_shelf_filter_changed("1990")
        QApplication.processEvents()
        assert _visible(view) == {"1990s"}

    def test_clearing_restores_every_shelf(self, view):
        view._on_shelf_filter_changed("kids")
        QApplication.processEvents()
        view._on_shelf_filter_changed("")
        QApplication.processEvents()

        assert _visible(view) == {"Apple+ Kids", "Hindu Subs", "Comedy", "1990s"}

    def test_whitespace_only_counts_as_cleared(self, view):
        view._on_shelf_filter_changed("   ")
        QApplication.processEvents()
        assert len(_visible(view)) == 4

    def test_no_match_hides_everything_without_crashing(self, view):
        view._on_shelf_filter_changed("zzzznope")
        QApplication.processEvents()
        assert _visible(view) == set()


class TestItDoesNotDamageState:

    def test_filtering_never_moves_a_shelf_between_zones(self, view):
        """A pinned shelf must still be pinned after filtering it out and back.

        Visibility and zone membership are different things; conflating them
        would silently unpin shelves as a side effect of typing.
        """
        from streamselect.gui.discover_groups import PINNED
        before = view._groups[PINNED].members()
        assert [w._shelf_key for w in before] == ["decade:1990"]

        view._on_shelf_filter_changed("comedy")
        QApplication.processEvents()
        view._on_shelf_filter_changed("")
        QApplication.processEvents()

        assert view._groups[PINNED].members() == before

    def test_a_zone_with_a_match_stays_on_screen(self, view):
        view._on_shelf_filter_changed("1990")
        QApplication.processEvents()
        from streamselect.gui.discover_groups import PINNED
        assert view._groups[PINNED].isVisible(), (
            "hid the container of the only matching shelf — the match would be "
            "invisible despite matching"
        )


class TestTheControlIsUsable:
    """Project UI conventions, which exist because their absence is a papercut."""

    def test_it_has_a_clear_button_and_a_tooltip(self, view):
        v = view
        assert v._shelf_filter.isClearButtonEnabled(), (
            "filter inputs use setClearButtonEnabled(True) — project standard"
        )
        assert v._shelf_filter.toolTip(), "every control needs a tooltip"
        assert v._shelf_filter.placeholderText()

    def test_the_filter_is_not_persisted(self):
        """A filter restored at launch shows a near-empty Discover with no
        visible cause, which reads as a broken app rather than a preference."""
        import inspect

        src = inspect.getsource(DiscoverView._on_shelf_filter_changed)
        assert "config" not in src and "save" not in src
