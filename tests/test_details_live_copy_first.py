"""VERS-1: the details pane shows a live copy first.

User report (screenshots): opening "President Curtis" from the
Watch Queue's Alerts Matched row rendered the copy on "Delta Shared" (an
EXPIRED source) as primary — Play, Watch Later, poster, "Source: Delta
Shared" — while the only PLAYABLE copy (Birch, active) sat collapsed under
"Also Available". User report: "the birch version was buried under Also
Available but it was the only available enabled and online version."

the project rules's "Engine/control/view layering" rule makes a disabled/expired/
orphaned source an absolute gate for forward-looking views
(``ProviderRepository.get_hidden_provider_ids()``); engaged views (History /
Favorites / Queue / Alerts) are the documented exception and may legitimately
hand the details pane a dead copy's id. ``resolve_live_copy()``
(``core/repositories/channel_live_copy.py``) is the one chokepoint that
redirects such a request to the best LIVE sibling of the same title — the
same ``content_key`` grouping and ``preference_engine.version_score`` ranking
the "Other Versions" list already uses for ``is_preferred``.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from streamselect.core.database import ChannelDB, ProviderDB
from streamselect.core.repositories import RepositoryFactory
from streamselect.core.repositories.channel_live_copy import resolve_live_copy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _provider(session, pid: str, *, is_active: bool = True, name: str | None = None) -> None:
    session.add(ProviderDB(
        id=pid, name=name or pid, type="xtream", url="http://example.com",
        username="u", password="p", is_active=is_active,
    ))
    session.flush()


def _channel(session, *, cid: str, name: str, provider_id: str, content_key: str,
             media_type: str = "series", is_hidden: bool = False,
             detected_prefix: str | None = None) -> ChannelDB:
    ch = ChannelDB(
        id=cid, source_id=str(uuid.uuid4()), provider_id=provider_id, name=name,
        media_type=media_type, content_key=content_key, is_hidden=is_hidden,
        detected_prefix=detected_prefix,
    )
    session.add(ch)
    session.flush()
    return ch


def _config(**overrides) -> SimpleNamespace:
    """Minimal duck-typed Config for ``preference_engine.version_score`` (and,
    for the show_channel_details_by_id test, ``update_details_pane_for_channel``'s
    ``metadata_auto_fetch`` gate)."""
    base = {
        "preferred_version_prefixes": [],
        "preferred_version_provider_ids": [],
        "preferred_version_quality": "",
        "metadata_auto_fetch": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _make_run_query(db):
    """Stand-in for ``_AsyncMixin._run_query`` that runs *query_fn* synchronously
    against a real session and hands the result straight to *on_result* — no
    executor, no Qt signal, matching how ``test_qa_checklist_navigation.py``
    drives the seam."""
    def _run_query(query_fn, on_result, *, token_ref=None, on_error=None, commit=False):
        try:
            with db.session_scope(commit=commit) as session:
                data = query_fn(RepositoryFactory(session))
        except Exception as exc:  # pragma: no cover - defensive, mirrors the real seam
            if on_error:
                on_error(exc)
            return
        on_result(data)
    return _run_query


# ---------------------------------------------------------------------------
# resolve_live_copy()
# ---------------------------------------------------------------------------

def test_a_dead_copy_resolves_to_its_live_sibling(db):
    with db.session_scope() as session:
        _provider(session, "p_dead", is_active=False, name="Delta Shared")
        _provider(session, "p_live", is_active=True, name="Birch")
        _channel(session, cid="p_dead_c1", name="President Curtis",
                 provider_id="p_dead", content_key="president-curtis")
        _channel(session, cid="p_live_c1", name="President Curtis",
                 provider_id="p_live", content_key="president-curtis")

    with db.session_scope() as session:
        repos = RepositoryFactory(session)
        live_copy = resolve_live_copy(repos, "p_dead_c1", config=_config())

    assert live_copy.dto.id == "p_live_c1"
    assert live_copy.redirected_from is not None
    assert live_copy.redirected_from.id == "p_dead_c1"
    assert live_copy.dead_source_name == "Delta Shared"
    assert live_copy.dead_source_state == "disabled"


def test_a_live_copy_is_returned_as_is(db):
    with db.session_scope() as session:
        _provider(session, "p_live", is_active=True, name="Birch")
        _channel(session, cid="c1", name="Some Movie", provider_id="p_live",
                 content_key="some-movie", media_type="movie")

    with db.session_scope() as session:
        repos = RepositoryFactory(session)
        live_copy = resolve_live_copy(repos, "c1", config=_config())

    assert live_copy.dto.id == "c1"
    assert live_copy.redirected_from is None
    assert live_copy.dead_source_name is None
    assert live_copy.dead_source_state is None


def test_a_dead_copy_with_no_live_sibling_still_resolves_but_says_so(db):
    with db.session_scope() as session:
        _provider(session, "p_dead", is_active=False, name="Delta Shared")
        _channel(session, cid="c1", name="Obscure Title", provider_id="p_dead",
                 content_key="obscure-title")

    with db.session_scope() as session:
        repos = RepositoryFactory(session)
        live_copy = resolve_live_copy(repos, "c1", config=_config())

    assert live_copy.dto.id == "c1"
    assert live_copy.redirected_from is None
    assert live_copy.dead_source_name == "Delta Shared"
    assert live_copy.dead_source_state == "disabled"


def test_the_best_live_sibling_is_the_preferred_one(db):
    from streamselect.core.preference_engine import version_score

    with db.session_scope() as session:
        _provider(session, "p_dead", is_active=False, name="Delta Shared")
        _provider(session, "p_a", is_active=True, name="A")
        _provider(session, "p_b", is_active=True, name="B")
        _channel(session, cid="c_dead", name="Show", provider_id="p_dead",
                 content_key="show")
        _channel(session, cid="c_a", name="Show", provider_id="p_a",
                 content_key="show", detected_prefix="FR")
        _channel(session, cid="c_b", name="Show", provider_id="p_b",
                 content_key="show", detected_prefix="EN")

    cfg = _config(preferred_version_prefixes=["EN"])

    with db.session_scope() as session:
        repos = RepositoryFactory(session)
        score_a = version_score(repos.channels.get_by_id("c_a"), cfg)
        score_b = version_score(repos.channels.get_by_id("c_b"), cfg)
        live_copy = resolve_live_copy(repos, "c_dead", config=cfg)

    assert score_a != score_b, "the scenario must actually rank the two siblings"
    expected_winner = "c_a" if score_a > score_b else "c_b"
    assert live_copy.dto.id == expected_winner


# ---------------------------------------------------------------------------
# show_channel_details_by_id() — the render seam
# ---------------------------------------------------------------------------

def test_show_channel_details_by_id_renders_the_live_copy(db):
    with db.session_scope() as session:
        _provider(session, "p_dead", is_active=False, name="Delta Shared")
        _provider(session, "p_live", is_active=True, name="Birch")
        _channel(session, cid="p_dead_c1", name="President Curtis",
                 provider_id="p_dead", content_key="president-curtis")
        _channel(session, cid="p_live_c1", name="President Curtis",
                 provider_id="p_live", content_key="president-curtis")

    from streamselect.gui.main_window_metadata import _MetadataMixin

    host = _MetadataMixin.__new__(_MetadataMixin)
    host.db = db
    host.config = _config()
    host._details_channel_token = [0]
    host._details_urls_token = [0]
    host.details_pane = MagicMock()
    host.details_pane.provider_name.return_value = "Birch"
    host._run_query = _make_run_query(db)

    host.show_channel_details_by_id("p_dead_c1")

    host.details_pane.show_channel.assert_called_once()
    shown_dto = host.details_pane.show_channel.call_args[0][0]
    assert shown_dto.id == "p_live_c1", (
        "the pane must render the LIVE copy, never the dead one an engaged "
        "row asked for"
    )

    host.details_pane.set_source_notice.assert_called_once()
    notice = host.details_pane.set_source_notice.call_args[0][0]
    assert notice is not None
    assert "Delta Shared" in notice
    assert "Birch" in notice


# ---------------------------------------------------------------------------
# DetailsPaneWidget.set_source_notice — the pane's dim line
# ---------------------------------------------------------------------------

def _pane(owned_widgets):
    from streamselect.core.config import Config
    from streamselect.gui.details_pane import DetailsPaneWidget
    pane = owned_widgets.own(DetailsPaneWidget(Config(), image_cache=MagicMock(), db=None))
    # _action_bar is its own top-level (not parented under pane) — see
    # tests/conftest.py's ``owned_widgets`` / ``destroy_widget`` note on the
    # QT-1 leak guard; owning it too keeps this new test off the allowlist.
    owned_widgets.own(pane._action_bar)
    return pane


def test_set_source_notice_shows_and_hides_the_line(qtbot, owned_widgets):
    pane = _pane(owned_widgets)
    pane.set_source_notice("Shown from Birch — your Delta Shared copy is disabled")
    assert not pane._source_notice_lbl.isHidden()
    assert "Birch" in pane._source_notice_lbl.text()

    pane.set_source_notice(None)
    assert pane._source_notice_lbl.isHidden()
