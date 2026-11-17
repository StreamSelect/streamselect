"""Which sources a channel load covers is resolved in the worker, not on the UI thread.

At launch the UI-thread read waited on a database connection for 1.3 s while
background threads opened theirs (watchdog, 2026-11-17).
"""

from __future__ import annotations

import threading

from streamselect.core.database import ProviderDB
from streamselect.core.repositories import RepositoryFactory
from streamselect.gui.channel_load_scope import SourceRow, provider_scope, with_provider_scope


def _scope(sources, given=None, excluded=()):
    return provider_scope(sources, given_provider_id=given, excluded_ids=set(excluded),
                          default_icon="D")


A = SourceRow("a", True, False, "A")
B = SourceRow("b", True, True, "")
OFF = SourceRow("off", False, False, "O")


def test_all_active_sources_shown_means_no_source_filter_and_badges():
    out = _scope([A, B, OFF])
    assert out["provider_id"] is None
    assert out["show_provider_icon"] is True
    assert out["provider_icon_map"] == {"a": "A", "b": "D", "off": "O"}, "no icon falls back"
    assert out["force_adult_ids"] == ["b"]
    assert out["has_any_provider"] is True


def test_one_active_source_is_that_source_without_badges():
    out = _scope([A, OFF])
    assert out["provider_id"] == "a" and out["show_provider_icon"] is False
    assert out["provider_icon_map"] == {}


def test_unticking_a_source_lists_the_rest_and_unticking_all_lists_none():
    assert _scope([A, B], excluded={"b"})["provider_id"] == ["a"]
    assert _scope([A, B], excluded={"a", "b"})["provider_id"] is None


def test_a_given_source_wins_and_no_sources_says_so():
    assert _scope([A, B], given="b")["provider_id"] == "b"
    assert _scope([])["has_any_provider"] is False


def test_the_worker_reads_the_sources_from_the_database_off_the_calling_thread(db):
    with db.session_scope() as s:
        s.add(ProviderDB(id="p1", name="One", type="xtream", url="http://example.com", is_active=True, icon="X"))
        s.add(ProviderDB(id="p2", name="Two", type="xtream", url="http://example.com", is_active=False))
    params = {"given_provider_id": None, "page_size": 10}
    out: dict = {}

    def work():
        with db.session_scope(commit=False) as s:
            out.update(with_provider_scope(RepositoryFactory(s), params,
                                           excluded_ids=set(), default_icon="D"))

    t = threading.Thread(target=work)
    t.start()
    t.join()
    assert out["provider_id"] == "p1", "the one active source"
    assert out["has_any_provider"] is True and out["page_size"] == 10
    assert "provider_id" not in params, "the UI thread's dict is never written"


def test_load_channels_opens_no_database_session_on_the_ui_thread():
    """The read moved into the worker: load_channels itself never calls get_session."""
    import ast
    import inspect
    import textwrap

    from streamselect.gui.main_window_channels import _ChannelListMixin
    tree = ast.parse(textwrap.dedent(inspect.getsource(_ChannelListMixin.load_channels)))
    calls = {n.func.attr for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "get_session" not in calls and "session_scope" not in calls
    assert "with_provider_scope" in ast.unparse(tree)
