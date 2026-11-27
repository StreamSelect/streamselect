"""Tools ▸ Library breakdown (design "Library Breakdown", BV-Q1-Q13).

The reads run on a real file database; the view is the real widget, driven
through a synchronous stand-in for the host's ``_run_query`` seam, and the
assertions are on what is laid out and what a click hands the host.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QLabel

from streamselect.core import library_breakdown as lb
from streamselect.core import sports_catalog as sc
from streamselect.core.database import ChannelDB, ProviderDB
from streamselect.core.games.models import SportTeamDB
from streamselect.core.repositories import RepositoryFactory

NOW = datetime(2026, 11, 27, 20, 0)


def _ch(s, cid, name, sport, *, source=None, league=None, view="sports", provider="p1", category="C"):
    s.add(ChannelDB(id=cid, source_id=cid, provider_id=provider, name=name, media_type="live",
                    special_view=view, sport_type=sport, sport_from=source, league_name=league,
                    category=category))


@pytest.fixture
def library(db):
    with db.session_scope() as s:
        s.add(ProviderDB(id="p1", name="One", type="xtream", url="http://example.com", username="u",
                         password="p", is_active=True))
        s.add(ProviderDB(id="off", name="Off", type="xtream", url="http://example.com", username="u",
                         password="p", is_active=False))
        _ch(s, "h1", "NHL: Flames vs Oilers", "hockey", source=sc.FROM_LEAGUE, league="NHL")
        _ch(s, "h2", "Hockey night", "hockey", source=sc.FROM_WORD)
        _ch(s, "s1", "Soccer: A v B", "soccer", source=sc.FROM_WORD)
        _ch(s, "s2", "Soccer: C v D", "soccer", source=sc.FROM_WORD)
        _ch(s, "s3", "Premier League: E v F", "soccer", source=sc.FROM_LEAGUE_GUESS, league="Premier League")
        _ch(s, "n1", "SKY SPORTS 1", sc.NETWORK)
        _ch(s, "x1", "PPV 4", sc.SLOT, view="ppv")
        _ch(s, "e1", "IT| PRIM 1 [LIVE-EVENT]", None, view="live_event")
        _ch(s, "u1", "NEXT | TORONTO VS BOSTON | Fri", sc.UNKNOWN, category="ESPN+ PPV")
        _ch(s, "u2", "NEXT | KARLSKRONA HK - TYRINGE SOSS | Fri", sc.UNKNOWN, category="SE PPV")
        _ch(s, "u3", "NEXT | BORAS HC - KALIX HC | Fri", sc.UNKNOWN, category="SE PPV")
        _ch(s, "u4", "US (Peacock 004) | Free Dance (2026-11-27 22:00:00)", sc.UNKNOWN, category="PEACOCK")
        _ch(s, "gone", "NHL: hidden source", "hockey", source=sc.FROM_LEAGUE, league="NHL", provider="off")
        for league, name, confirmed in (("hockey/NHL", "Toronto Maple Leafs", True),
                                        ("hockey/NHL", "Boston Bruins", True),
                                        ("hockey/NHL", "Liga", False),
                                        ("basketball/NBA", "Toronto Raptors", True),
                                        ("basketball/NBA", "Boston Celtics", True)):
            s.add(SportTeamDB(league_key=league, name=name, first_seen=NOW, last_seen=NOW,
                              last_in_game=NOW if confirmed else None))
    return db


def _read(db, fn, **kw):
    with db.session_scope(commit=False) as s:
        return fn(s, **kw)


def test_the_sports_read_counts_visible_sources_and_says_how_each_sport_was_decided(library):
    data = _read(library, lb.sports_breakdown)
    assert data.total == 12, "the disabled source's row is never counted (BV-Q13)"
    assert data.kinds == {lb.SPORT: 5, sc.NETWORK: 1, sc.SLOT: 1, sc.UNKNOWN: 4, lb.NONE: 1}
    assert [s.key for s in data.sports] == ["soccer", "hockey"], "largest first"
    soccer = data.sports[0]
    assert soccer.decided_by == ((sc.FROM_WORD, 2), (sc.FROM_LEAGUE_GUESS, 1))
    assert data.first_sport == "hockey", "the Sports view's order decides where it opens"
    assert data.teams["hockey/NHL"] == (("Boston Bruins", True), ("Toronto Maple Leafs", True),
                                        ("Liga", False)), "confirmed first"
    nhl = next(r for r in data.leagues["hockey"] if r.name == "NHL")
    assert (nhl.channels, nhl.confirmed, nhl.unconfirmed) == (1, 2, 1)


def test_the_catch_all_groups_what_nothing_identified_by_what_would_fix_it(library):
    data = _read(library, lb.catch_all)
    assert data.total == 4
    assert [(n, set(ls)) for n, ls in data.either] == [("NEXT | TORONTO VS BOSTON | Fri", {"NHL", "NBA"})]
    assert [(g.collection, g.games) for g in data.strangers] == [("SE PPV", 2)]
    assert data.not_games == ("US (Peacock 004) | Free Dance (2026-11-27 22:00:00)",)


def test_a_clicked_count_finds_exactly_its_visible_channels(library):
    assert sorted(_read(library, lb.channel_ids, sport="hockey")) == ["h1", "h2"]
    assert _read(library, lb.channel_ids, sport="hockey", league="") == ["h2"]
    assert _read(library, lb.channel_ids, kind=lb.NONE) == ["e1"]
    assert sorted(_read(library, lb.channel_ids, collection="SE PPV")) == ["u2", "u3"]


# ── the view ─────────────────────────────────────────────────────────────


@pytest.fixture
def view(library, qapp, owned_widgets):
    from streamselect.gui.library_breakdown_view import LibraryBreakdownView

    def run_query(fn, on_result, *, token_ref=None, on_error=None, commit=False):
        with library.session_scope(commit=commit) as s:
            result = fn(RepositoryFactory(s))
        on_result(result)

    v = owned_widgets.own(LibraryBreakdownView(SimpleNamespace(config=None, _run_query=run_query)))
    v.resize(1400, 1000)
    v.show()
    v.on_activate()
    qapp.processEvents()
    return v


def _labels(widget, text):
    return [w for w in widget.findChildren(QLabel) if w.text() == text and w.isVisible()]


def _click(widget):
    widget.mouseReleaseEvent(QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(widget.rect().center()),
                                         Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                                         Qt.KeyboardModifier.NoModifier))


def test_it_opens_on_hockey_with_the_selection_bold_and_the_others_links(view):
    from streamselect.gui.analytics_parts import LinkLabel

    hockey = _labels(view, "Hockey")
    soccer = _labels(view, "Soccer")
    assert hockey and not isinstance(hockey[0], LinkLabel), "the selected sport is plain bold text"
    assert soccer and isinstance(soccer[0], LinkLabel), "another sport is a link"
    assert _labels(view, "Hockey · leagues") and _labels(view, "NHL · teams")


def test_confirmed_teams_are_laid_out_above_the_unconfirmed_ones(view, qapp):
    qapp.processEvents()
    confirmed = _labels(view, "Boston Bruins")[0]
    heading = _labels(view, "Unconfirmed: named in listings, no game found yet")[0]
    liga = _labels(view, "Liga")[0]
    y = lambda w: w.mapTo(view, w.rect().topLeft()).y()      # noqa: E731
    assert y(confirmed) < y(heading) < y(liga)


def test_clicking_a_sport_shows_its_leagues_and_a_count_opens_its_channels(view, qapp):
    _click(_labels(view, "Soccer")[0])
    qapp.processEvents()
    assert _labels(view, "Soccer · leagues"), "the right column follows the selection"
    got = []
    view.browse_requested.connect(lambda label, ids: got.append((label, sorted(ids))))
    _click(_labels(view, "3")[0])               # soccer's channel count
    assert got == [("Soccer", ["s1", "s2", "s3"])]
