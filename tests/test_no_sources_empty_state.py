"""Behavioral tests for the content area's empty states (an earlier change, onboarding 4).

Bug: a fresh install with zero configured sources showed the SAME message as a
normal filtered-to-zero result — "No channels match — try a different search
or check filter settings" — which blames search/filters for a cause that is
actually "there is no source yet". This drives the REAL production code
(``MainWindow._build_empty_state_panel`` / ``_sync_empty_state`` /
``load_channels`` / ``_on_channels_loaded``) against a real file-backed
``Database`` (never ``:memory:`` — see the project rules Tests rule) and asserts
rendered widget STATE (``isVisible()``/``isEnabled()``) plus the real
click→handler wiring, not just that a string constant exists somewhere.

Two scenarios, matching the PR's acceptance criteria:

1. Zero sources configured at all → the honest "no sources" banner shows, its
   "Add Source" button is visible + enabled, and clicking it invokes the SAME
   ``add_provider`` handler the sidebar '+' / Sources-manager '+' buttons use
   (asserted via the real connection, not a re-implementation).
2. >=1 source configured but zero matching channels → the ORIGINAL filter/
   search message and stats text are unchanged, and the no-sources banner
   stays hidden — this is the guard that stops the new state leaking into
   ordinary "no results" use.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QApplication, QLineEdit, QListView, QVBoxLayout, QWidget

from streamselect.core.database import Database, ProviderDB
from streamselect.core.repositories import RepositoryFactory


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _seed_provider(db: Database, name: str = "TestProv") -> str:
    """Insert a real ProviderDB row and return its id."""
    pid = str(uuid.uuid4())
    with db.session_scope() as session:
        session.add(ProviderDB(
            id=pid,
            name=name,
            type="xtream",
            url="http://example.com:8080",
            username="u1",
            password="pass",
            is_active=True,
            urls=[{"url": "http://example.com:8080", "priority": 0,
                   "is_active": True, "success_count": 0, "failure_count": 0}],
        ))
    return pid


def _make_channel_load_host(qapp, db: Database):
    """A bare MainWindow host wired for a REAL load_channels()/_on_channels_loaded()
    pass: _run_query runs query_fn synchronously against the real file DB (mirrors
    the established _inline_run_query pattern in test_explore_entry_points.py)
    instead of a background executor, so the whole pipeline — including the real
    _query_channels worker and the real _build_empty_state_panel()-constructed
    panel — executes deterministically in-process.
    """
    from streamselect.gui import main_window as mw_module
    from streamselect.gui.channel_list_model import ChannelListModel

    win = mw_module.MainWindow.__new__(mw_module.MainWindow)
    win.db = db

    # Real virtualized model/view (load_channels populates these directly).
    win.channel_model = ChannelListModel()
    win.channels_list = QListView()
    win.channels_list.setModel(win.channel_model)

    # Real banner widgets — mirrors what setup_ui() builds, minus the rest of
    # the window chrome. _build_no_sources_banner() is the REAL production
    # method (main_window_providers.py), not a re-implementation. The container
    # is stashed on win so it (and its children) stay alive for the test's
    # lifetime — an unreferenced top-level QWidget is eligible for GC as soon
    # as this function returns, which would invalidate the banner underneath it.
    container = QWidget()
    win._test_list_container = container
    win._list_layout = QVBoxLayout(container)
    from PyQt6.QtWidgets import QLabel
    from tests.conftest import wire_channel_banner_widgets
    wire_channel_banner_widgets(win)
    win.add_provider = MagicMock()  # the handler under test — real button must call THIS
    win.switch_to_sources_manager = MagicMock()
    # The REAL production panel (main_window_empty_state.py).
    win._build_empty_state_panel()
    container.show()
    win.channels_list.show()

    # Rendered-state surfaces (real widgets, not MagicMock, so .text()/
    # .currentMessage() reflect what the user would actually see).
    win.stats_label = QLabel()
    from PyQt6.QtWidgets import QStatusBar
    win.status_bar = QStatusBar()

    # Minimal main-thread UI state load_channels() reads before dispatch.
    win.all_channels = ["stale"]
    win.config = MagicMock()
    win.config.global_filter_paused = True          # short-circuits exclusion resolution
    win.config.collapse_variants_in_list = False
    # Must be a NON-EMPTY (truthy) dict: `current_filter_state or (... hasattr(self,
    # 'filter_panel') ...)` short-circuits on a truthy dict — an empty {} instead
    # falls through to hasattr() on this bare __new__'d host, which PyQt turns into
    # RuntimeError (no filter_panel attr AND __init__ never ran; see the an earlier change/an earlier change
    # trap documented on _sources_status_target in main_window_providers.py).
    win.current_filter_state = {
        "_language_prefixes": [], "_region_prefixes": [],
        "_platform_prefixes": [], "_quality_prefixes": [],
    }
    win.search_input = QLineEdit()
    win._search_debounce = MagicMock()
    win._bypass_tier1_filters = False
    win._bypass_global_exclusions = False
    win._details_genre_filter = None
    win._details_person_filter = None
    win._details_tag_filter = None
    win._details_category_filter = None
    win._details_id_filter = None
    win._id_filter_show_all = False
    win._search_page_size = 1000
    win._hidden_mode = False
    win._load_channels_token = [0]

    # _on_channels_loaded() stubs unrelated to the empty-state branch under test.
    win._enqueue_tmdb_enrichment = MagicMock()
    win._clear_provider_busy = MagicMock()

    def _inline_run_query(query_fn, on_result, *, token_ref=None, on_error=None):
        """Mirror MainWindow._run_query inline against the REAL file db."""
        if token_ref is not None:
            token_ref[0] += 1
        with db.session_scope(commit=False) as session:
            data = query_fn(RepositoryFactory(session))
        on_result(data)

    win._run_query = _inline_run_query
    return win


# ---------------------------------------------------------------------------
# 1. Zero sources configured — honest message + wired, enabled, visible button
# ---------------------------------------------------------------------------

def _know_sources(host, db) -> None:
    """What load_providers records (``_sync_no_source_notice``), without its notice."""
    with db.session_scope(commit=False) as session:
        host._source_availability = RepositoryFactory(session).providers.get_availability()
    host._sync_empty_state()


def _panel_text(host) -> str:
    panel = host._empty_state_panel
    return f"{panel.headline.text()} {panel.hint.text()}"


def test_zero_sources_shows_honest_state_with_enabled_visible_add_button(qapp, file_db):
    host = _make_channel_load_host(qapp, file_db)  # file_db has ZERO providers
    host.load_channels()
    _know_sources(host, file_db)

    panel = host._empty_state_panel
    assert panel.isVisible()
    assert "no source" in _panel_text(host).lower()
    (btn,) = panel.buttons()
    assert btn.text() == "Add Source" and btn.isVisible() and btn.isEnabled()
    # Honest cause, never blames search/filters.
    assert "search" not in host.status_bar.currentMessage().lower()
    assert "filter" not in host.status_bar.currentMessage().lower()
    assert "source" in host.stats_label.text().lower()
    assert host._first_source_pending, "the first-run hand-off to Discover is armed"

    # The button invokes the SAME handler every other Add Source button uses.
    host.add_provider.assert_not_called()
    btn.click()
    host.add_provider.assert_called_once()


def test_the_panel_starts_hidden(qapp, file_db):
    host = _make_channel_load_host(qapp, file_db)
    assert not host._empty_state_panel.isVisible()


def test_the_no_source_state_survives_a_view_switch(qapp, file_db):
    """The old banner was hidden by every view switch, so at launch — which
    switches to the list after loading — a new user never saw it."""
    host = _make_channel_load_host(qapp, file_db)
    host.load_channels()
    _know_sources(host, file_db)
    host._hide_channel_banners()          # what _hide_all_content_views runs
    assert host._empty_state_panel.isVisible()


# ---------------------------------------------------------------------------
# 2. >=1 source configured, zero matching channels — the list's own states
# ---------------------------------------------------------------------------

def test_sources_exist_zero_channels_says_the_source_has_none(qapp, file_db):
    _seed_provider(file_db)  # a real source exists; it just has no channels yet

    host = _make_channel_load_host(qapp, file_db)
    host.load_channels()
    _know_sources(host, file_db)

    # The status-line message is unchanged.
    assert host.status_bar.currentMessage() == (
        "No channels match — try a different search or check filter settings"
    )
    assert host.stats_label.text() == "Showing 0 of 0"
    # The panel says what is true, never "add a source".
    assert "has no channels" in _panel_text(host)
    assert [b.text() for b in host._empty_state_panel.buttons()] == ["Open Sources"]


def test_a_search_with_no_results_names_the_search(qapp, file_db):
    _seed_provider(file_db)
    host = _make_channel_load_host(qapp, file_db)
    host.search_input.blockSignals(True)
    host.search_input.setText("dune")
    host.search_input.blockSignals(False)
    host.load_channels()
    _know_sources(host, file_db)
    assert "No results for \u201cdune\u201d" in _panel_text(host)
    (btn,) = host._empty_state_panel.buttons()
    btn.click()
    assert host.search_input.text() == "", "Clear search clears the search"


def test_a_new_sources_first_load_outranks_the_lists_own_state(qapp, file_db):
    pid = _seed_provider(file_db, name="Example IPTV")
    host = _make_channel_load_host(qapp, file_db)
    host._first_loading = {pid: "Example IPTV"}
    host.load_channels()
    _know_sources(host, file_db)
    assert "Loading Example IPTV" in _panel_text(host)
    assert host._empty_state_panel.buttons() == []


def test_the_panel_never_sits_over_the_sources_screen(qapp, file_db, owned_widgets):
    host = _make_channel_load_host(qapp, file_db)
    # The other tests' hosts die with the function. The watcher below holds a
    # bound method of this one, so its parentless widgets must be freed by hand.
    for widget in (host._test_list_container, host.channels_list, host.stats_label,
                   host.status_bar, host.search_input, host._channel_banner,
                   host._channel_filter_bar, host._channel_exclusion_btn,
                   host._channel_filter_btn, host._channel_adult_btn):
        owned_widgets.own(widget)
    manager = owned_widgets.own(QWidget())
    host.sources_manager_view = manager
    host._watch_views_for_empty_state()
    _know_sources(host, file_db)
    assert host._empty_state_panel.isVisible()
    manager.show()
    qapp.processEvents()
    assert not host._empty_state_panel.isVisible(), "the user is already fixing it there"
    manager.hide()
    qapp.processEvents()
    assert host._empty_state_panel.isVisible()
