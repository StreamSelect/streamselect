"""Collapsed Discover shelves as tiles (design "Discover's Collapsed Shelves", A).

Owner: the collapsed shelves were long single-column lists of names with half
the view empty. Each is now a tile (four newest posters, name, title count) in a
grid that fills the width; clicking one opens the shelf as a row where it was;
hovering a poster shows its title.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from streamselect.core.discovery_engine import ContentCard
from streamselect.gui.discover_groups import GENRES

GENRE_KEYS = [f"genre:G{i}" for i in range(6)]


def _settle():
    for _ in range(4):
        QApplication.processEvents()


@pytest.fixture()
def view(qapp, owned_widgets, tmp_path):
    from streamselect.core.config import Config
    from streamselect.gui.discover_view import DiscoverView
    from streamselect.gui.discover_workers import _ShelfData

    cfg = Config(config_dir=tmp_path)
    cfg.discover_zones_seeded = True
    v = owned_widgets.own(DiscoverView(MagicMock(), cfg, MagicMock()))
    v.resize(1000, 1600)
    for key in GENRE_KEYS:
        v._on_shelf_ready(_ShelfData(key.split(":")[1], key, [], header_only=True))
    v._flush_pending_collapsed()
    v.show()
    _settle()
    return v


def _y(view, w):
    _settle()
    return w.mapTo(view, QPoint(0, 0)).y()


def _tiles(view):
    return [view._shelf_widgets[k].tile for k in GENRE_KEYS]


def test_collapsed_shelves_are_tiles_filling_the_width_in_columns(view):
    tiles = _tiles(view)
    assert all(t.isVisible() for t in tiles)
    assert not any(view._shelf_widgets[k].isVisible() for k in GENRE_KEYS), "no one-line rows"
    grid = tiles[0].parentWidget()
    xs = sorted({t.x() for t in tiles})
    assert len(xs) >= 3, f"several columns at 1000 px, got {len(xs)}"
    assert len({t.width() for t in tiles}) == 1, "every tile the same width"
    right = max(t.x() + t.width() for t in tiles)
    assert grid.width() - right <= 2, f"the row is filled: {grid.width() - right} px left over"


def test_clicking_a_tile_opens_the_shelf_as_a_row_where_it_was(view):
    view._start_expand_fetch = lambda key: None
    tiles = _tiles(view)
    QTest.mouseClick(tiles[2], Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
    _settle()
    row = view._shelf_widgets["genre:G2"]
    assert row.isVisible() and not row._collapsed and not tiles[2].isVisible()
    assert _y(view, tiles[1]) < _y(view, row) < _y(view, tiles[3]), "the grid splits around the row"
    assert [w._shelf_key for w in view._groups[GENRES].members()] == GENRE_KEYS, "nothing moved"


def test_a_tile_shows_titles_on_hover_and_its_count(view):
    tile = _tiles(view)[0]
    cards = [ContentCard(channel_id=f"c{i}", title=f"Film {i}", media_type="movie", thumbnail_url=None,
                         rating=None, year=None, genre=None) for i in range(5)]
    tile.set_preview(cards, 17_300)
    assert [s.toolTip() for s in tile.slots] == ["Film 0", "Film 1", "Film 2", "Film 3"]
    assert tile.count_lbl.text() == "17.3k titles"
    assert tile.has_preview


def test_the_shelf_filter_hides_a_tile(view):
    view._on_shelf_filter_changed("G4")
    _settle()
    assert [k for k in GENRE_KEYS if view._shelf_widgets[k].tile.isVisible()] == ["genre:G4"]
    view._on_shelf_filter_changed("")
    _settle()
    assert all(t.isVisible() for t in _tiles(view))


def test_a_preview_is_the_newest_titles_and_the_count_after_exclusions(tmp_path):
    from streamselect.core.config import Config
    from streamselect.core.database import ChannelDB, Database, ProviderDB
    from streamselect.core.shelf_preview import shelf_preview

    db = Database(f"sqlite:///{tmp_path / 'p.db'}")
    db.create_tables()
    with db.session_scope() as s:
        s.add(ProviderDB(id="p1", name="P", type="xtream", url="http://x.example.com", is_active=True))
        for i in range(6):
            for prefix in ("EN", "XX"):                         # XX is excluded below
                s.add(ChannelDB(id=str(uuid.uuid4()), source_id=str(uuid.uuid4()), provider_id="p1",
                                name=f"{prefix} - Horror {i}", detected_title=f"Horror {i}", detected_prefix=prefix,
                                media_type="movie", detected_genres=["Horror"], detected_added=1000 + i,
                                content_key=f"horror {i}|movie", raw_data={}))
    fk = {"excluded_prefixes": ["XX"], "include_uncategorized": True}
    with db.session_scope(commit=False) as s:
        cards, count = shelf_preview(s, Config(config_dir=tmp_path), "genre:Horror", fk=fk, af={}, ek={})
    assert [c.title for c in cards] == ["Horror 5", "Horror 4", "Horror 3", "Horror 2"], "newest first"
    assert count == 6, "one per title, excluded copies left out"


def test_a_tile_name_stands_out_from_its_posters(view):
    tile = _tiles(view)[0]
    tile.name_lbl.ensurePolished()
    assert tile.name_lbl.font().weight() >= 600, "semi-bold (owner: names were lost among posters)"
    assert tile.name_lbl.font().pixelSize() > tile.count_lbl.font().pixelSize() or \
        tile.name_lbl.font().pointSizeF() > tile.count_lbl.font().pointSizeF()


def test_a_reload_returns_to_where_the_page_was(view, monkeypatch):
    """A finished background re-read reloads Discover; it used to land the user at the top."""
    from PyQt6.QtCore import QObject, pyqtSignal

    from streamselect.gui import discover_view as dv
    from streamselect.gui.discover_workers import _ShelfData

    class _Loader(QObject):                     # the real loader's signals, the same shelves
        shelfReady = pyqtSignal(object)
        cardsReady = pyqtSignal(str, list)
        finished = pyqtSignal()

        def __init__(self, *a, **k):
            super().__init__()

        def cancel(self):
            pass

        def run(self):
            for key in GENRE_KEYS:
                self.shelfReady.emit(_ShelfData(key.split(":")[1], key, [], header_only=True))
            self.finished.emit()

    monkeypatch.setattr(dv, "_LoaderWorker", _Loader)
    view._on_load_finished()                    # the page as a finished load leaves it
    view._loading_lbl.hide()
    view.resize(1000, 300)
    _settle()
    bar = view._page_scroll.verticalScrollBar()
    bar.setValue(bar.maximum())
    before = bar.value()
    assert before > 0
    view._active = True
    view.refresh()
    for _ in range(200):
        QApplication.processEvents()
        if view._loaded and bar.value() == before:
            break
    assert view._loaded and bar.value() == before, f"back at {before}, got {bar.value()}"


def test_opening_or_collapsing_a_row_never_reloads_the_tiles_posters(view):
    """Owner: collapsing Recently Added, or opening and closing the 2000s, blanked and
    reloaded every poster on the other tiles of that section."""
    from PyQt6.QtGui import QPixmap

    cache = view._image_cache
    delivered = {}
    cache.subscribe.side_effect = lambda url, cb, *a: delivered.setdefault(url, cb)
    tiles = _tiles(view)
    for i, t in enumerate(tiles):
        t.set_preview([ContentCard(channel_id=f"c{i}{j}", title=f"T{i}{j}", media_type="movie",
                                   thumbnail_url=f"http://img.example.com/{i}/{j}.jpg", rating=None,
                                   year=None, genre=None) for j in range(4)], 10)
    poster = QPixmap(200, 300)
    for url, cb in list(delivered.items()):
        cb(url, poster)
    _settle()
    asked = cache.get_image_async.call_count
    view._start_expand_fetch = lambda key: None
    view._on_expand_requested("genre:G1")          # open a row: the grid splits around it
    _settle()
    view._on_collapse_requested("genre:G1")        # and back
    _settle()
    assert cache.get_image_async.call_count == asked, "no poster asked for again"
    others = [t for k, t in zip(GENRE_KEYS, tiles) if k != "genre:G1"]
    assert all(s.pixmap() is not None and not s.pixmap().isNull() for t in others for s in t.slots)
