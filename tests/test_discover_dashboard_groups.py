"""Discover as a dashboard (design "Discover as Your Dashboard", rev 2).

The page reads in six groups: Pinned, Your lists, Discover's shelves, Genres,
Decades (this decade a year at a time), Provider Categories. A shelf's zone is its
state, its group is its place: collapsing leaves it where it is, pinning lifts it to
the top, unpinning puts it back. Your lists (Watch Later, Recommended, the Watch
Queue) open by default, for a new profile and, once, for a returning one.
"""

from __future__ import annotations

import uuid
from collections import Counter
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication

from streamselect.gui.discover_groups import (
    APP, CATEGORIES, DECADES, GENRES, GROUPS, LISTS, PINNED, group_of, seed_dashboard_defaults,
)

# ── the Decades group's shelves ──────────────────────────────────────────


def test_this_decade_is_a_year_at_a_time_and_earlier_ones_are_decades():
    from streamselect.core.discovery_engine import time_shelf_keys

    counts = Counter({2026: 9, 2025: 40, 2024: 3, 2021: 12, 2019: 4, 2015: 2, 1994: 30, 1951: 4})
    assert time_shelf_keys(counts, 2026) == [
        "year:2026", "year:2025", "year:2021",          # 2024 holds 3: under the floor of 5
        "decade:2010", "decade:1990",                   # 2019 + 2015 = 6; the 1950s hold 4
    ]


def test_a_year_shelf_holds_only_its_year(tmp_path):
    from streamselect.core.database import ChannelDB, Database, ProviderDB
    from streamselect.gui.discover_workers import browse_title_for_key, fetch_cards_for_key

    db = Database(f"sqlite:///{tmp_path / 'y.db'}")
    db.create_tables()
    with db.session_scope() as s:
        s.add(ProviderDB(id="p1", name="P", type="xtream", url="http://x.example.com", is_active=True))
        for year in (2024, 2025, 2025):
            s.add(ChannelDB(id=str(uuid.uuid4()), source_id=str(uuid.uuid4()), provider_id="p1",
                            name=f"Film {uuid.uuid4().hex[:6]}", media_type="movie", detected_rating=7.0,
                            raw_data={"releaseDate": f"{year}-05-01", "rating": "7"}))
    with db.session_scope(commit=False) as s:
        cards = fetch_cards_for_key(s, MagicMock(), "year:2025", 30, sk={}, fk={}, af={},
                                    ek={"excluded_provider_ids": None})
    assert sorted(c.year for c in cards) == [2025, 2025]
    assert browse_title_for_key("year:2025") == "2025"


# ── the Watch Queue shelf ───────────────────────────────────────────────


def test_the_queue_shelf_is_its_films_and_series_in_queue_order(tmp_path):
    from streamselect.core.database import ChannelDB, Database, ProviderDB, WatchQueueDB
    from streamselect.core.discover_queue_shelf import get_queue_cards

    db = Database(f"sqlite:///{tmp_path / 'q.db'}")
    db.create_tables()
    with db.session_scope() as s:
        s.add(ProviderDB(id="p1", name="P", type="xtream", url="http://x.example.com", is_active=True))
        s.add(ProviderDB(id="p2", name="Q", type="xtream", url="http://y.example.com", is_active=False))
        rows = [("film-b", "movie", "p1"), ("show", "series", "p1"), ("news", "live", "p1"),
                ("film-a", "movie", "p1"), ("gone", "movie", "p2")]
        for cid, media, pid in rows:
            s.add(ChannelDB(id=cid, source_id=cid, provider_id=pid, name=cid, detected_title=cid,
                            media_type=media, raw_data={}))
        queue = [("film-b", "movie", None), ("show", "series", "ep1"), ("news", "live", None),
                 ("show", "series", "ep2"), ("film-a", "movie", None), ("gone", "movie", None)]
        for pos, (cid, media, ep) in enumerate(queue):
            s.add(WatchQueueDB(channel_id=cid, channel_name=cid, media_type=media, position=pos, episode_id=ep))
    with db.session_scope(commit=False) as s:
        cards = get_queue_cards(s, excluded_provider_ids=["p2"])
    assert [c.channel_id for c in cards] == ["film-b", "show", "film-a"], (
        "queue order; two queued episodes are their series once; live and a hidden source left out")


# ── the loader's order ──────────────────────────────────────────────────


def test_the_loader_sends_the_groups_in_page_order_with_region_chips(tmp_path):
    from streamselect.core.config import Config
    from streamselect.core.database import ChannelDB, Database, ProviderDB
    from streamselect.gui.discover_workers import _LoaderWorker, _ZoneSnapshot

    db = Database(f"sqlite:///{tmp_path / 'l.db'}")
    db.create_tables()
    with db.session_scope() as s:
        s.add(ProviderDB(id="p1", name="P", type="xtream", url="http://x.example.com", is_active=True))
        for i in range(12):
            s.add(ChannelDB(id=f"c{i}", source_id=f"c{i}", provider_id="p1", name=f"Film {i}",
                            media_type="movie", detected_rating=7.0, detected_genres=["Drama"],
                            detected_collection="KOMEDIE", detected_collection_group="KOMEDIE",
                            detected_region="PL", user_category="Watch Later" if i < 2 else None,
                            raw_data={"releaseDate": "1994-01-01", "rating": "7"}))
    got = []
    worker = _LoaderWorker(db, Config(config_dir=tmp_path), _ZoneSnapshot(first_launch=True))
    worker.shelfReady.connect(got.append)
    worker.run()
    keys = [d.shelf_key for d in got]
    order = [g for g, _ in GROUPS]
    assert [order.index(group_of(k)) for k in keys] == sorted(order.index(group_of(k)) for k in keys), keys
    assert keys[0] == "user_cat:Watch Later", "Your lists lead with Watch Later"
    assert {"genre:Drama", "decade:1990", "collection:KOMEDIE"} <= set(keys)
    assert next(d for d in got if d.shelf_key == "collection:KOMEDIE").chips == ("PL",), (
        "the loader passes a category's region chips through to the view")


# ── defaults ────────────────────────────────────────────────────────────


def test_a_returning_profile_gets_your_lists_open_once(tmp_path):
    from streamselect.core.config import Config

    cfg = Config(config_dir=tmp_path)
    cfg.discover_zones_seeded = True
    cfg.discover_expanded_shelves = ["top_movies"]
    cfg.discover_hidden_shelves = ["queue"]
    seed_dashboard_defaults(cfg)
    assert cfg.discover_expanded_shelves == ["top_movies", "recommended", "user_cat:Watch Later"], (
        "a hidden shelf stays hidden")
    cfg.discover_expanded_shelves = ["top_movies"]           # the user collapses them again
    seed_dashboard_defaults(cfg)
    assert cfg.discover_expanded_shelves == ["top_movies"], "it runs once"


# ── the page ────────────────────────────────────────────────────────────


@pytest.fixture()
def page(qapp, owned_widgets, tmp_path):
    from streamselect.core.config import Config
    from streamselect.gui.discover_view import DiscoverView
    from streamselect.gui.discover_workers import _ShelfData

    cfg = Config(config_dir=tmp_path)
    cfg.discover_zones_seeded = True
    cfg.discover_pinned_shelves = ["year:2026", "recently_added"]
    cfg.discover_more_expanded = True
    view = owned_widgets.own(DiscoverView(MagicMock(), cfg, MagicMock()))
    view.resize(900, 1400)
    for key in ["user_cat:Watch Later", "recommended", "queue", "recently_added", "top_movies",
                "genre:Comedy", "genre:Drama", "genre:Horror", "year:2026", "year:2025", "decade:1990",
                "collection:KOMEDIE"]:
        view._on_shelf_ready(_ShelfData(key, key, [], header_only=key not in cfg.discover_pinned_shelves))
    view._flush_pending_collapsed()
    view._loaded = True
    view._update_group_heads()
    view.show()
    QApplication.processEvents()
    return view


def _y(view, w):
    for _ in range(3):              # nested layouts settle over a few passes
        QApplication.processEvents()
    return w.mapTo(view, QPoint(0, 0)).y()


def _keys(view, group):
    return [w._shelf_key for w in view._groups[group].members()]


def test_the_groups_stack_in_page_order_on_screen(page):
    ys = [_y(page, page._groups[g]) for g, _ in GROUPS]
    assert all(page._groups[g].isVisible() for g, _ in GROUPS)
    assert ys == sorted(ys) and len(set(ys)) == len(ys), f"top to bottom as designed: {ys}"
    assert _keys(page, PINNED) == ["year:2026", "recently_added"], "pinned follows the pinned list's order"
    assert _keys(page, LISTS) == ["user_cat:Watch Later", "recommended", "queue"]
    assert _keys(page, APP) == ["top_movies"]
    assert _keys(page, DECADES) == ["year:2025", "decade:1990"]
    assert _keys(page, CATEGORIES) == ["collection:KOMEDIE"]


def test_collapsing_or_opening_keeps_a_shelf_in_its_place(page):
    page._start_expand_fetch = lambda key: None
    page._on_expand_requested("genre:Drama")
    QApplication.processEvents()
    assert _keys(page, GENRES) == ["genre:Comedy", "genre:Drama", "genre:Horror"]
    assert not page._shelf_widgets["genre:Drama"]._collapsed
    page._on_collapse_requested("genre:Drama")
    assert _keys(page, GENRES) == ["genre:Comedy", "genre:Drama", "genre:Horror"]


def test_pinning_lifts_a_shelf_and_unpinning_puts_it_back(page):
    page._start_expand_fetch = lambda key: None
    page._on_pin_requested("genre:Drama")
    QApplication.processEvents()
    assert _keys(page, PINNED)[-1] == "genre:Drama" and "genre:Drama" not in _keys(page, GENRES)
    assert _y(page, page._shelf_widgets["genre:Drama"]) < _y(page, page._groups[LISTS]), "pinned is on top"
    page._on_unpin_requested("genre:Drama")
    assert _keys(page, GENRES) == ["genre:Comedy", "genre:Drama", "genre:Horror"], "back at its place"


def test_a_heading_folds_its_group_states_its_count_and_remembers(page):
    genres = page._groups[GENRES]
    assert genres.heading.text().endswith("(3)") and genres.body.isVisible()
    decades_before = _y(page, page._groups[DECADES])
    genres.heading.click()
    QApplication.processEvents()
    assert not genres.body.isVisible() and genres.isVisible(), "the heading stays, the rows go"
    assert page._config.discover_folded_groups == [GENRES]
    assert _y(page, page._groups[DECADES]) < decades_before, "the page closes up under the heading"
    genres.heading.click()
    assert genres.body.isVisible() and page._config.discover_folded_groups == []


def test_every_group_but_pinned_folds_from_its_heading(page):
    from PyQt6.QtWidgets import QPushButton

    assert not isinstance(page._groups[PINNED].heading, QPushButton), "Pinned never folds"
    lists = page._groups[LISTS]
    assert lists.heading.text() == "Your Shelves  (3)"
    lists.heading.click()
    QApplication.processEvents()
    assert not lists.body.isVisible() and page._config.discover_folded_groups == [LISTS]
    assert page._groups[APP].heading.text().startswith("Discover's Shelves")


def test_manage_changes_apply_shelf_by_shelf_without_a_rebuild(page):
    page._start_expand_fetch = lambda key: None
    before = dict(page._shelf_widgets)
    cfg = page._config
    cfg.discover_expanded_shelves = ["genre:Horror"]            # Manage: Watch Later collapsed, Horror opened
    cfg.discover_pinned_shelves = ["recently_added", "year:2026"]   # Manage: Up / Down
    page._apply_zone_config(set(cfg.discover_hidden_shelves))
    QApplication.processEvents()
    assert page._shelf_widgets["user_cat:Watch Later"] is before["user_cat:Watch Later"], "not rebuilt"
    assert page._shelf_widgets["user_cat:Watch Later"]._collapsed
    assert not page._shelf_widgets["genre:Horror"]._collapsed
    assert _keys(page, PINNED) == ["recently_added", "year:2026"]
    assert cfg.discover_expanded_shelves == ["genre:Horror"], "saved from what is on screen"


def test_opening_several_shelves_loads_each_in_turn(page):
    started = []
    page._inflight_expand = "genre:Comedy"            # one fetch already running
    real = type(page)._start_expand_fetch
    page._stop_loader = lambda *a: None
    for key in ("genre:Drama", "genre:Horror"):
        real(page, key)
    assert page._expand_queue == ["genre:Drama", "genre:Horror"], "queued, not cancelled"
    page._start_expand_fetch = started.append
    page._on_expand_cards_ready("genre:Comedy", [])
    QApplication.processEvents()
    assert started == ["genre:Drama"] and page._expand_queue == ["genre:Horror"]


def test_a_refresh_asked_for_during_a_load_runs_after_it(page):
    class _Running:
        def isRunning(self):
            return True
    page._thread = _Running()
    page.refresh()
    assert page._refresh_pending, "remembered, not dropped"
    page._thread = None
    calls = []
    page.refresh = lambda: calls.append(1)
    page._on_load_finished()
    QApplication.processEvents()
    assert calls == [1]
