"""Right-click on a Discover shelf (its row header or its tile): the usual actions,
and for a shelf the user made, its delete (owner request, 2026-11-28).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox


@pytest.fixture()
def view(qapp, owned_widgets, tmp_path):
    from streamselect.core.config import Config
    from streamselect.gui.discover_view import DiscoverView
    from streamselect.gui.discover_workers import _ShelfData

    cfg = Config(config_dir=tmp_path)
    cfg.discover_zones_seeded = True
    v = owned_widgets.own(DiscoverView(MagicMock(), cfg, MagicMock()))
    for key, title in (("user_cat:Roger Corman", "Roger Corman"), ("recipe:Cold Drama", "✦ Cold Drama"),
                       ("genre:Horror", "Horror")):
        v._on_shelf_ready(_ShelfData(title, key, [], header_only=True))
    v._flush_pending_collapsed()
    return v


def _menu_texts(view, key, monkeypatch) -> list[str]:
    from streamselect.gui.discover_shelf_menu import show_shelf_menu
    seen = []
    monkeypatch.setattr(QMenu, "exec", lambda self, *a: seen.extend(a.text() for a in self.actions()))
    show_shelf_menu(view, key, None)
    return [t for t in seen if t]


def test_every_shelf_gets_the_usual_actions_and_only_yours_get_delete(view, monkeypatch):
    genre = _menu_texts(view, "genre:Horror", monkeypatch)
    assert genre == ["Expand Horror", "Pin to top", "See all", "Hide this shelf"]
    assert _menu_texts(view, "user_cat:Roger Corman", monkeypatch)[-1] == "Delete list…"
    recipe = _menu_texts(view, "recipe:Cold Drama", monkeypatch)
    assert "Edit recipe…" in recipe and recipe[-1] == "Delete recipe…"


def test_right_clicking_a_tile_or_a_header_opens_the_menu(view, monkeypatch):
    from PyQt6.QtCore import QPoint
    from PyQt6.QtGui import QContextMenuEvent

    asked = []
    monkeypatch.setattr("streamselect.gui.discover_shelf_menu.show_shelf_menu",
                        lambda v, key, pos: asked.append(key))
    shelf = view._shelf_widgets["user_cat:Roger Corman"]
    ev = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(5, 5), QPoint(5, 5))
    QApplication.sendEvent(shelf.tile, ev)
    QApplication.sendEvent(shelf, QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(5, 5), QPoint(5, 5)))
    assert asked == ["user_cat:Roger Corman", "user_cat:Roger Corman"]


@pytest.mark.parametrize("answer, sent", [(QMessageBox.StandardButton.Yes, ["Roger Corman"]),
                                          (QMessageBox.StandardButton.No, [])])
def test_deleting_a_list_asks_first(view, monkeypatch, answer, sent):
    from streamselect.gui.discover_shelf_menu import _delete
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: answer)
    got = []
    view.userListDeleteRequested.connect(got.append)
    _delete(view, "user_cat:Roger Corman", "Roger Corman")
    assert got == sent


def test_a_deleted_list_leaves_its_titles_and_no_other_list(tmp_path):
    from streamselect.core.database import ChannelDB, Database, ProviderDB
    from streamselect.core.repositories import RepositoryFactory

    db = Database(f"sqlite:///{tmp_path / 'l.db'}")
    db.create_tables()
    with db.session_scope() as s:
        s.add(ProviderDB(id="p1", name="P", type="xtream", url="http://x.example.com", is_active=True))
        for i, cat in enumerate(["Roger Corman", "Roger Corman", "Watch Later"]):
            s.add(ChannelDB(id=f"c{i}", source_id=f"c{i}", provider_id="p1", name=f"F{i}",
                            media_type="movie", user_category=cat, category_mood="neutral"))
    with db.session_scope() as s:
        assert RepositoryFactory(s).channels.delete_user_category("Roger Corman") == 2
    with db.session_scope(commit=False) as s:
        rows = {c.id: c.user_category for c in s.query(ChannelDB)}
    assert rows == {"c0": None, "c1": None, "c2": "Watch Later"}, "titles kept, only that list gone"


def test_a_recipe_is_deleted_by_name_with_its_shelf_state(tmp_path):
    from streamselect.core.config import Config
    from streamselect.gui.recipe_saved_mixin import _RecipeSavedMixin

    class Host(_RecipeSavedMixin):
        def __init__(self):
            self._config = Config(config_dir=tmp_path)
            self._config.saved_recipes = [{"name": "Cold Drama"}, {"name": "Keep"}]
            self._config.discover_pinned_shelves = ["recipe:Cold Drama"]
            self.savedRecipesChanged = MagicMock()
            self._load_saved_recipes = lambda: None

    h = Host()
    h.delete_saved_recipe_by_name("Cold Drama")
    assert [r["name"] for r in h._config.saved_recipes] == ["Keep"]
    assert h._config.discover_pinned_shelves == []
    h.savedRecipesChanged.emit.assert_called_once()


def test_the_host_deletes_the_list_and_lifts_its_exclusion(tmp_path):
    from streamselect.core.config import Config
    from streamselect.core.database import ChannelDB, Database, ProviderDB
    from streamselect.core.repositories import RepositoryFactory
    from streamselect.gui.discover_shelf_menu import delete_user_list

    db = Database(f"sqlite:///{tmp_path / 'h.db'}")
    db.create_tables()
    with db.session_scope() as s:
        s.add(ProviderDB(id="p1", name="P", type="xtream", url="http://x.example.com", is_active=True))
        s.add(ChannelDB(id="c0", source_id="c0", provider_id="p1", name="F", media_type="movie",
                        user_category="Trash"))

    class Host:
        def __init__(self):
            self.config = Config(config_dir=tmp_path)
            self.config.global_filter_excluded_user_categories = ["Trash", "Adult"]
            self.status = MagicMock()
            self.load_favorites, self.load_channels = MagicMock(), MagicMock()
            self.discover_view = MagicMock()

        def _run_query(self, fn, on_result, *, commit=False, on_error=None, token_ref=None):
            with db.session_scope(commit=commit) as s:
                on_result(fn(RepositoryFactory(s)))

    h = Host()
    delete_user_list(h, "Trash")
    with db.session_scope(commit=False) as s:
        assert s.get(ChannelDB, "c0").user_category is None
    assert h.config.global_filter_excluded_user_categories == ["Adult"]
    h.discover_view.reload.assert_called_once()
    assert "1 title kept" in h.status.call_args[0][0]
