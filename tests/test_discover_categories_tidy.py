"""Discover's categories, tidied (design "Tidying Discover's Categories", Plans 1-2).

Plan 1: a collection label loses its "UK|" head, a source's continent folder and a
leading country name (the region stays, as a chip), and Discover lists films and
series by default — live TV packages behind a remembered "Live categories" switch.
Plan 2: near-identical spellings share one shelf (``detected_collection_group``).
The provider's own ``category`` is never changed.
"""

from __future__ import annotations

import uuid

import pytest

from streamselect.core.category_headings import collection_group_key, read_category
from tests.test_collection_token_cleanup import _add_channel, _add_provider, _get, _run_ingestion, file_db  # noqa: F401


@pytest.mark.parametrize("category, label, code", [
    ("UK| MAX PPV VIP", "MAX PPV VIP", "UK"),
    ("|EN| ANIME", "ANIME", "EN"),                         # the old marker shape, unchanged
    ("DENMARK DISNEY+ PPV", "DISNEY+ PPV", "DEN"),
    ("AM| CANADA HD", "CANADA HD", None),                  # the Americas folder, never Armenia
    ("MULTI| MOVIES", "MOVIES", None),                     # a multi-track word, not a place
    ("BEE| BEIN SPORTS", "BEE| BEIN SPORTS", None),        # an unknown head stays
    ("ACTION | AVENTURE", "ACTION | AVENTURE", None),      # a pipe inside a name stays
    ("KOMEDIE", "KOMEDIE", None),
])
def test_a_category_reads_as_a_clean_label_and_its_region(category, label, code):
    clean, marker = read_category(category, frozenset({"AM"}))
    assert (clean, marker.code if marker else None) == (label, code)


def test_near_identical_spellings_share_a_key_and_different_names_do_not():
    assert collection_group_key("HORROR / THRILLER") == collection_group_key("HORROR/THRILLERS") \
        == collection_group_key("Horror Thriller")
    assert collection_group_key("COMEDIA") == collection_group_key("COMEDIAS") == collection_group_key("COMÉDIA")
    assert collection_group_key("COMEDY") != collection_group_key("COMEDIA"), "a translation is Plan 3, not 2"
    assert collection_group_key("NETFLIX ORIGINALS") == collection_group_key("NETFLIX ORIGINAL")


def test_ingestion_stores_the_clean_label_and_its_shelf_key_and_keeps_the_category(file_db):  # noqa: F811
    _add_provider(file_db)
    uk = _add_channel(file_db, name="EN - Some Film", category="UK| NETFLIX ORIGINAL")
    es = _add_channel(file_db, name="ES - Otra Película", category="ES| NETFLIX ORIGINALS")
    _run_ingestion(file_db)
    a, b = _get(file_db, uk), _get(file_db, es)
    assert (a.detected_collection, b.detected_collection) == ("NETFLIX ORIGINAL", "NETFLIX ORIGINALS")
    assert a.detected_collection_group == b.detected_collection_group == "NETFLIX ORIGINAL"
    assert a.detected_collection_language == "UK", "the head disagrees with the name's EN: it stays as a chip"
    assert a.category == "UK| NETFLIX ORIGINAL", "the provider's category is never changed"


# ── Discover's queries ───────────────────────────────────────────────────


@pytest.fixture
def shelves_db(tmp_path):
    from streamselect.core.database import ChannelDB, Database, ProviderDB

    db = Database(f"sqlite:///{tmp_path / 'tidy.db'}")
    db.create_tables()
    with db.session_scope() as s:
        s.add(ProviderDB(id="p1", name="P", type="xtream", url="http://x.example.com", is_active=True))

        def add(n, label, region, media="movie"):
            for i in range(n):
                s.add(ChannelDB(id=str(uuid.uuid4()), source_id=f"{label}{region}{i}", provider_id="p1",
                                name=f"{label} {i}", media_type=media, detected_collection=label,
                                detected_collection_group=collection_group_key(label), detected_region=region,
                                raw_data={"rating": "7.0", "stream_icon": ""}))
        add(3, "HORROR / THRILLER", "PL")
        add(2, "HORROR/THRILLERS", "DE")
        add(2, "KOMEDIE", "PL")
        add(4, "MAX PPV VIP", "UK", media="live")
    return db


def test_one_shelf_per_group_titled_by_its_commonest_label_with_its_regions(shelves_db):
    from streamselect.core.discovery_engine import get_all_collections

    with shelves_db.session_scope(commit=False) as s:
        got = get_all_collections(s)
    assert [(c.key, c.title, c.regions) for c in got] == [
        ("HORROR THRILLER", "HORROR / THRILLER", ("PL", "DE")), ("KOMEDIE", "KOMEDIE", ("PL",))]


def test_live_packages_are_categories_only_when_asked(shelves_db):
    from streamselect.core.discovery_engine import get_all_collections, get_by_collection

    with shelves_db.session_scope(commit=False) as s:
        assert "MAX PPV VIP" not in {c.key for c in get_all_collections(s)}
        assert "MAX PPV VIP" in {c.key for c in get_all_collections(s, include_live=True)}
        assert get_by_collection(s, "MAX PPV VIP") == []
        assert len(get_by_collection(s, "MAX PPV VIP", include_live=True)) >= 1
        horror = get_by_collection(s, "HORROR THRILLER")
    assert len(horror) == 5, "both spellings' films are the one shelf's"


def test_a_search_shelf_is_keyed_by_the_group_and_titled_by_the_label():
    from streamselect.gui.search_posters import resolve_shelf_target

    t = resolve_shelf_target(category="PL| HORROR/THRILLERS", collection="HORROR/THRILLERS",
                             collection_key="HORROR THRILLER")
    assert (t.name, t.key) == ("HORROR/THRILLERS", "collection:HORROR THRILLER")


# ── the view ─────────────────────────────────────────────────────────────


def test_a_collection_shelf_shows_its_regions_after_its_title(qapp, owned_widgets, tmp_path):
    from PyQt6.QtCore import QPoint

    from streamselect.core.config import Config
    from streamselect.gui.discover_shelf import _Shelf

    shelf = owned_widgets.own(_Shelf("HORROR / THRILLER", "collection:HORROR THRILLER", [], None,
                                     Config(config_dir=tmp_path), collapsed=True, chips=("PL", "DE")))
    shelf.resize(900, 60)
    shelf.show()
    qapp.processEvents()
    assert [c.text() for c in shelf.region_chips] == ["PL", "DE"]
    x = lambda w: w.mapTo(shelf, QPoint(0, 0)).x()       # noqa: E731
    title_end = x(shelf._title_lbl) + shelf._title_lbl.width()
    assert all(c.isVisible() and x(c) >= title_end for c in shelf.region_chips), "after the name, on its row"
    assert x(shelf.region_chips[0]) < x(shelf.region_chips[1])


def test_the_live_categories_switch_is_remembered_and_reloads(qapp, owned_widgets, tmp_path):
    from PyQt6.QtWidgets import QPushButton

    from streamselect.core.config import Config
    from streamselect.gui.discover_shelf import more_categories_row

    class _View:                       # the row reads only these from the view
        def __init__(self):
            self._config = Config(config_dir=tmp_path)
            self._more_btn = QPushButton("More Categories")
            self.reloads = 0

        def reload(self):
            self.reloads += 1

    view = _View()
    row = owned_widgets.own(more_categories_row(view))
    assert not view.live_categories_chip.is_enabled(), "off by default: Discover is films and series"
    view.live_categories_chip.click()
    assert view._config.discover_show_live_collections is True and view.reloads == 1
    assert view._more_btn.parent() is row
