"""The five empty states, worded once (confirmed R6 table)."""
from __future__ import annotations

from datetime import datetime

import pytest

from streamselect.core.repositories.dtos import SourceAvailability
from streamselect.gui.empty_state import EmptyState, empty_state_text


def test_no_source_names_the_cause_and_offers_the_fix():
    none = SourceAvailability(total=0, usable=0, turned_off=0, expired=0)
    headline, hint, action = empty_state_text(EmptyState.NO_SOURCE, avail=none)
    assert headline == "Nothing to show yet: there's no source to read from."
    assert "No sources available" in hint and action == "add"

    expired = SourceAvailability(total=1, usable=0, turned_off=0, expired=1,
                                 last_expired_at=datetime(2026, 3, 14))
    _, hint, action = empty_state_text(EmptyState.NO_SOURCE, avail=expired)
    assert "expired on" in hint and action == "open"


def test_first_load_names_the_source():
    headline, hint, action = empty_state_text(EmptyState.FIRST_LOAD, names=["Example IPTV"])
    assert headline == "Loading Example IPTV…"
    assert "as they arrive" in hint and action is None


@pytest.mark.parametrize(("sources", "headline"), [
    (1, "This source has no channels."), (3, "Your sources have no channels.")])
def test_nothing_here(sources, headline):
    assert empty_state_text(EmptyState.NOTHING_HERE, sources=sources)[0] == headline


def test_no_results_quotes_the_search():
    headline, _, action = empty_state_text(EmptyState.NO_RESULTS, query="dune")
    assert headline == "No results for “dune”." and action == "clear_search"


@pytest.mark.parametrize(("hidden", "headline"), [
    (1, "1 title is hidden by your filters."),
    (1412, "1,412 titles are hidden by your filters.")])
def test_filtered_counts_what_is_hidden(hidden, headline):
    assert empty_state_text(EmptyState.FILTERED, hidden=hidden)[0] == headline
