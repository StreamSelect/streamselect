"""Search's Posters button and saving results as a shelf (user report).

The grid has to show what the list holds, and a saved search has to stay live.
Geometry is asserted on the painted widgets, and saved searches run on a real
file database, because the query is what makes them live.
"""
from __future__ import annotations


import pytest
from PyQt6.QtWidgets import QLabel, QWidget

from streamselect.core.config import Config
from streamselect.core.database import ChannelDB, MetadataDB, ProviderDB
from streamselect.core.discovery_engine import ContentCard
from streamselect.core.repositories.dtos import ChannelListDTO
from streamselect.gui.channel_list_model import ChannelListModel
from streamselect.gui.discover_card import UniformCardGrid
from streamselect.gui.discover_workers import _cards_for_saved_recipe
from streamselect.gui.search_posters import card_from_list_row, resolve_shelf_target
from tests.conftest import destroy_widget


# ── What saving does ─────────────────────────────────────────────────────

def test_a_collection_alone_pins_its_existing_shelf():
    target = resolve_shelf_target(category="|EN| ITALIAN MOVIES / ENG SUB",
                                  collection="ITALIAN MOVIES / ENG")
    assert target.key == "collection:ITALIAN MOVIES / ENG"


@pytest.mark.parametrize("tag, key", [
    (("genre", "Drama"), "genre:Drama"),
    (("platform", "Netflix"), "platform:Netflix"),
    (("decade", "1990s"), "decade:1990"),
])
def test_a_facet_with_a_shelf_pins_it(tag, key):
    assert resolve_shelf_target(tag=tag).key == key


def test_a_person_saves_because_discover_has_no_shelf_per_person():
    target = resolve_shelf_target(person="Nicolas Cage")
    assert target.key == ""
    assert target.includes == {"person": {"Nicolas Cage"}}


def test_words_always_save_and_keep_the_filters():
    target = resolve_shelf_target(search=" tron ", genre="Drama", tag_includes={"language": {"English"}})
    assert target.key == ""
    assert target.search == "tron"
    assert target.includes == {"genre": {"Drama"}, "language": {"English"}}
    assert target.name == "tron · Drama · English"


def test_words_inside_a_collection_keep_the_exact_category():
    target = resolve_shelf_target(search="amore", category="|EN| ITALIAN", collection="ITALIAN")
    assert target.key == "" and target.category == "|EN| ITALIAN" and target.search == "amore"


def test_a_collection_with_more_filters_is_not_the_plain_shelf():
    target = resolve_shelf_target(category="|EN| ITALIAN", collection="ITALIAN",
                                  tag_includes={"genre": {"Drama"}})
    assert target.key == "" and target.category == "|EN| ITALIAN"


def test_everything_is_not_a_shelf():
    assert resolve_shelf_target() is None


# ── A saved search is live ───────────────────────────────────────────────

def _add(db, cid, title, *, category="Movies", cast=None):
    """A channel with NO tags, as a title is before tagging reaches it."""
    with db.session_scope() as session:
        if session.get(ProviderDB, "p") is None:
            session.add(ProviderDB(id="p", name="Source", type="xtream", url="http://x",
                                   username="u", password="p", is_active=True, urls=[]))
        metadata_id = None
        if cast:
            metadata_id = f"m{cid}"
            session.add(MetadataDB(id=metadata_id, title=title, media_type="movie",
                                   cast=[{"name": cast}]))
        session.add(ChannelDB(id=cid, source_id=cid, provider_id="p", name=title, media_type="movie",
                              detected_title=title, category=category, metadata_id=metadata_id))


def _shelf(db, **recipe) -> list[str]:
    config = Config()
    config.saved_recipes = [{"name": "s", "includes": {}, "excludes": {}, **recipe}]
    with db.session_scope(commit=False) as session:
        return [c.title for c in _cards_for_saved_recipe(session, config, "s", 30)]


def test_a_saved_search_picks_up_titles_added_later(file_db):
    _add(file_db, "a", "Tron")
    assert _shelf(file_db, search="tron") == ["Tron"]
    _add(file_db, "b", "Tron Legacy")
    assert _shelf(file_db, search="tron") == ["Tron", "Tron Legacy"]


def test_a_saved_search_puts_the_best_match_first(file_db):
    _add(file_db, "a", "Astronaut")
    _add(file_db, "b", "Tron")
    assert _shelf(file_db, search="tron") == ["Tron", "Astronaut"]


def test_a_saved_search_puts_titles_before_cast_matches(file_db):
    """Alphabetically "cast" sorts first, so a weak cast hit outranked the title."""
    _add(file_db, "a", "Aardvark", cast="Patron Saint")
    _add(file_db, "b", "Tron")
    assert _shelf(file_db, search="tron") == ["Tron", "Aardvark"]


def test_the_search_list_loads_titles_before_cast_matches(file_db):
    """With more cast matches than a page, titles must not be pushed off it."""
    from streamselect.core.repositories.channel import ChannelRepository
    _add(file_db, "a", "Aardvark", cast="Patron Saint")
    _add(file_db, "b", "Tron")
    with file_db.session_scope(commit=False) as session:
        rows = ChannelRepository(session).get_all(search_query="tron", limit=1, offset=0)
        assert [c.id for c in rows] == ["b"]


def test_a_saved_search_matches_the_cast_as_the_search_box_does(file_db):
    _add(file_db, "a", "Face Off", cast="Nicolas Cage")
    _add(file_db, "b", "Unrelated")
    assert _shelf(file_db, search="nicolas cage") == ["Face Off"]


def test_a_saved_search_stays_inside_its_category(file_db):
    _add(file_db, "a", "Amore One", category="|EN| ITALIAN")
    _add(file_db, "b", "Amore Two", category="Other")
    assert _shelf(file_db, search="amore", category="|EN| ITALIAN") == ["Amore One"]


def test_an_empty_recipe_still_shows_nothing(file_db):
    _add(file_db, "a", "Tron")
    assert _shelf(file_db) == []


# ── The grid draws the list's rows ───────────────────────────────────────

def _row(cid, **kw) -> ChannelListDTO:
    base = {"id": cid, "name": f"EN - {cid}", "media_type": "movie", "provider_id": "p",
            "is_favorite": False, "category": "c", "quality": None, "detected_prefix": "EN",
            "detected_region": None, "detected_quality": None, "detected_year": "1999",
            "detected_title": cid}
    return ChannelListDTO(**{**base, **kw})


def test_a_list_row_becomes_the_card_it_describes():
    card = card_from_list_row(_row("Tron", poster_url="http://x/p.jpg", is_favorite=True,
                                   user_rating=1, detected_rating=7.5, watch_percent=40,
                                   variant_count=3, detected_genre="Sci-Fi"))
    assert (card.channel_id, card.title, card.thumbnail_url) == ("Tron", "Tron", "http://x/p.jpg")
    assert (card.year, card.rating, card.genre) == (1999, 7.5, "Sci-Fi")
    assert card.is_favorite and card.is_liked and card.variant_count == 3
    assert card.progress_fraction == pytest.approx(0.4)


def test_a_finished_title_shows_watched_not_progress():
    card = card_from_list_row(_row("x", watch_completed=True, watch_percent=99))
    assert card.already_watched and card.progress_fraction == 0.0


def test_an_unusable_year_and_rating_are_left_off():
    card = card_from_list_row(_row("x", detected_year="n/a", detected_rating=0))
    assert card.year is None and card.rating is None


def test_display_rows_follow_the_grouping_and_the_result_filter(qapp):
    model = ChannelListModel()
    model.set_channels([_row("Alpha"), _row("Beta", media_type="series")], provider_icon_map={},
                       show_provider_icon=False, has_more=False, query_params={})
    assert [c.id for _r, k, c in model.display_rows() if k == "channel"] == ["Alpha", "Beta"]

    model.set_grouped(True, collapsed_sections=["series"])
    kinds = [(k, c.id if c else None) for _r, k, c in model.display_rows()]
    assert kinds == [("header", None), ("channel", "Alpha"), ("header", None)], "collapse applies"

    model.set_grouped(False)
    model.set_result_filter("beta")
    assert [c.id for _r, k, c in model.display_rows() if k == "channel"] == ["Beta"]


# ── Rendered geometry: bands split the grid into runs ────────────────────

def _grid(container, cards, bands=()):
    grid = UniformCardGrid(container, item_w=100, item_h=150, spacing=10,
                           factory=lambda _c: QLabel(), band_factory=lambda _p: QLabel())
    grid.set_cards(cards, bands)
    return grid


def test_cards_restart_at_column_zero_below_a_band(qapp):
    host = QWidget()
    try:
        # 330 wide = 3 columns. Two cards, a band, then two more.
        grid = _grid(host, list("abcd"), [(0, "top", 30), (2, "mid", 30)])
        first, second, third = (grid.rect_for(i, 330) for i in (0, 1, 2))
        assert (first.x(), first.y()) == (0, 40), "the top band pushes the first row down"
        assert second.y() == first.y() and second.x() > first.x()
        assert third.x() == 0, "a band starts a new row even with columns free"
        assert third.y() == first.bottom() + 1 + 10 + 30 + 10
    finally:
        destroy_widget(host)


def test_a_band_is_painted_across_the_full_width_between_its_rows(qapp):
    host = QWidget()
    try:
        grid = _grid(host, list("abcd"), [(2, "mid", 30)])
        grid.sync(0, 2000, 330)
        band = grid._live_bands[0]
        assert band.width() == 330 and band.height() == 30
        assert grid.rect_for(1, 330).bottom() < band.y() < grid.rect_for(2, 330).top()
    finally:
        destroy_widget(host)


def test_the_height_counts_the_bands(qapp):
    host = QWidget()
    try:
        plain = _grid(host, list("abcd"))
        banded = _grid(host, list("abcd"), [(0, "a", 30), (2, "b", 30)])
        assert plain.total_height(330) == 150 * 2 + 10
        assert banded.total_height(330) == banded.rect_for(3, 330).bottom() + 1
    finally:
        destroy_widget(host)


def test_a_collapsed_section_at_the_end_still_has_height(qapp):
    host = QWidget()
    try:
        assert _grid(host, [], [(0, "only", 30)]).total_height(330) == 30
    finally:
        destroy_widget(host)


def test_a_grid_without_bands_is_the_plain_arithmetic(qapp):
    host = QWidget()
    try:
        grid = _grid(host, [ContentCard(str(i), str(i), "movie", None, None, None, None) for i in range(10)])
        assert grid.rect_for(4, 330).topLeft().x() == 110
        assert grid.rect_for(4, 330).y() == 160
        assert grid.visible_range(0, 150, 330)[0] == 0
    finally:
        destroy_widget(host)


def test_only_the_scrolled_to_run_is_materialized(qapp):
    host = QWidget()
    try:
        grid = _grid(host, list(range(300)), [(0, "a", 30), (150, "b", 30)])
        first, last = grid.visible_range(grid.rect_for(200, 330).y(), 300, 330)
        assert first <= 200 < last
        assert last - first < 60, "the live set follows the viewport, not the count"
    finally:
        destroy_widget(host)




def test_the_preference_lives_in_the_profile_store():
    assert Config.model_fields["search_view_posters"].json_schema_extra == {"store": "profile"}
