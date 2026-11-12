"""Search's Posters button: the same results as Discover's grid, and keeping them.

The grid draws what the channel list holds, read from the list's own model, so
every filter, section, sort and Whole/Part choice applies without this module
knowing about any of them. There is no second query and no second result set.

The grid is a CHILD OF THE LIST, covering it, rather than a sibling swapped in
beside it. The list is what every view switch shows and hides, and a child goes
with its parent, so a new view cannot forget about the grid.

Saving follows one rule: if what is on screen is already a shelf, pin that shelf.
Otherwise it is a saved recipe, which is already a live Discover shelf; search
words and a provider category are two more fields on it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from loguru import logger
from PyQt6.QtCore import QEvent, QObject, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from streamselect.core.discovery_engine import ContentCard
from streamselect.gui import channel_list_section_band as _band
from streamselect.gui import cursor_affordance
from streamselect.gui import deferred_config_save as _cfgsave
from streamselect.gui import icon_utils as _icon_utils
from streamselect.gui.channel_list_roles import CHANNEL_HTML_ROLE, SECTION_TYPE_ROLE
from streamselect.gui.discover_browse import _BrowseView
from streamselect.gui.discover_card import card_zoom_slider
from streamselect.gui.discover_workers import (
    _COLLECTION_PREFIX, _DECADE_PREFIX, _GENRE_PREFIX, _PLATFORM_PREFIX, _RECIPE_PREFIX,
)
from streamselect.gui.main_window_empty_state import _ShowHideWatcher
from streamselect.gui.recipe_saved_mixin import _RecipeSavedMixin

#: Facets Discover builds a shelf for, per value. People are not here: Discover
#: has one Featured Actor shelf, not one per person, so a person saves as a recipe.
_SHELF_PREFIX_BY_FACET: dict[str, str] = {
    "collection": _COLLECTION_PREFIX,
    "genre": _GENRE_PREFIX,
    "decade": _DECADE_PREFIX,
    "platform": _PLATFORM_PREFIX,
}

_PERSON_BAND_PAD_V = 10


@dataclass(frozen=True)
class ShelfTarget:
    """What the save button would do. A ``key`` means pin; none means save."""

    name: str
    key: str = ""
    includes: dict = field(default_factory=dict)
    excludes: dict = field(default_factory=dict)
    search: str = ""
    category: str = ""


def resolve_shelf_target(*, search: str = "", category: str = "", collection: str = "",
                         genre: str = "", person: str = "", tag=None,
                         tag_includes=None, tag_excludes=None) -> "ShelfTarget | None":
    """Decide how the results on screen become a shelf.

    Args:
        search: The search box's words.
        category: The collection chip's exact provider category.
        collection: That category's cleaned name, which is what its shelf is
            keyed by. The shelf can hold more than the chip: a few cleaned names
            cover several categories (user accepted this).
        genre: The genre chip's value.
        person: The person chip's value.
        tag: The tag chip's ``(facet, value)``.
        tag_includes: The filter panel's ``{facet: values}``.
        tag_excludes: The filter panel's excluded ``{facet: values}``.

    Returns:
        The target, or ``None`` when nothing narrows the list, because "everything"
        is not a shelf.
    """
    search = search.strip()
    includes = {f: set(v) for f, v in (tag_includes or {}).items() if v}
    excludes = {f: set(v) for f, v in (tag_excludes or {}).items() if v}
    chip = ("genre", genre) if genre else ("person", person) if person else tuple(tag or ())

    if not search and not includes and not excludes:
        if category and collection:
            return ShelfTarget(collection, key=f"{_COLLECTION_PREFIX}{collection}")
        if chip and chip[0] in _SHELF_PREFIX_BY_FACET:
            value = chip[1]
            # A decade tag reads "1990s"; its shelf key is the bare year.
            key_value = value.rstrip("s") if chip[0] == "decade" else value
            return ShelfTarget(value, key=f"{_SHELF_PREFIX_BY_FACET[chip[0]]}{key_value}")

    if chip:
        includes.setdefault(chip[0], set()).add(chip[1])
    if not (search or category or includes or excludes):
        return None
    parts = [search, collection or category,
             *sorted(v for values in includes.values() for v in values),
             *sorted(f"not {v}" for values in excludes.values() for v in values)]
    return ShelfTarget(" · ".join(p for p in parts if p), includes=includes,
                       excludes=excludes, search=search, category=category)


def card_from_list_row(row) -> ContentCard:
    """A channel-list row as a poster card, so Search's grid shows the same rows.

    The list's rows were already queried, filtered and ranked, so nothing is
    looked up again. Every field is one the row already holds.

    Args:
        row: A ``ChannelListDTO``.

    Returns:
        The card, with the badges the row's own state implies.
    """
    year = str(row.detected_year or "")
    completed = bool(row.watch_completed)
    rating = row.detected_rating
    return ContentCard(
        channel_id=row.id,
        title=row.detected_title or row.name,
        media_type=row.media_type,
        thumbnail_url=row.poster_url or None,
        rating=rating if rating is not None and 0 < rating < 10 else None,
        year=int(year) if year.isdigit() else None,
        genre=row.detected_genre,
        is_favorite=bool(row.is_favorite),
        already_watched=completed,
        is_liked=row.user_rating > 0,
        detected_prefix=row.detected_prefix or None,
        progress_fraction=0.0 if completed else (row.watch_percent or 0) / 100.0,
        variant_count=row.variant_count,
        content_key=row.content_key,
    )


class _PosterBand(QWidget):
    """A section or person heading between poster rows: the list's own row, drawn again."""

    clicked = pyqtSignal(object)            # the model index
    modeToggled = pyqtSignal(str, bool)     # section, word_only

    def __init__(self, model, row: int, kind: str) -> None:
        super().__init__()
        self._index = model.index(row)
        self._kind = kind
        cursor_affordance.set_clickable(self)
        if kind == "person":
            box = QHBoxLayout(self)
            box.setContentsMargins(8, 0, 8, 0)
            box.addWidget(QLabel(self._index.data(CHANNEL_HTML_ROLE) or ""))

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self._kind == "header":
            painter = QPainter(self)
            _band.paint_row(painter, self.rect(), self._index, self.font())
            painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        all_seg, word_seg = _band.toggle_rects_for(self.rect(), self._index, self.font())
        if all_seg.contains(pos) or word_seg.contains(pos):
            self.modeToggled.emit(self._index.data(SECTION_TYPE_ROLE) or "", word_seg.contains(pos))
        else:
            self.clicked.emit(self._index)


class _CoverParent(QObject):
    """Keeps a child sized to exactly cover its parent."""

    def __init__(self, child: QWidget) -> None:
        super().__init__(child)
        self._child = child

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt API)
        if event.type() == QEvent.Type.Resize:
            self._child.setGeometry(obj.rect())
        return False


class _SearchPostersMixin:
    """Search's poster grid and its save button (see module docstring)."""

    def _build_search_posters_controls(self, layout) -> None:
        """Add the size slider, save button and Posters button to Search's controls row."""
        self._poster_zoom = card_zoom_slider(self.config)
        self._poster_zoom.setToolTip("Resize posters. Discover uses the same size.")
        self._poster_zoom_timer = QTimer(self)
        self._poster_zoom_timer.setSingleShot(True)
        self._poster_zoom_timer.timeout.connect(self._apply_poster_zoom)
        self._poster_zoom.valueChanged.connect(lambda _v: self._poster_zoom_timer.start(300))
        layout.addWidget(self._poster_zoom)

        self._shelf_btn = QPushButton("Save as shelf")
        self._shelf_btn.setFlat(True)
        self._shelf_btn.setToolTip("Search or filter first: everything at once is not a shelf")
        self._shelf_btn.clicked.connect(self._on_shelf_btn_clicked)
        layout.addWidget(self._shelf_btn)

        self._posters_btn = QPushButton()
        self._posters_btn.setFlat(True)
        self._posters_btn.clicked.connect(self._toggle_search_posters)
        layout.addWidget(self._posters_btn)

        self._poster_refresh_timer = QTimer(self)
        self._poster_refresh_timer.setSingleShot(True)
        self._poster_refresh_timer.setInterval(30)
        self._poster_refresh_timer.timeout.connect(self._refresh_poster_grid)
        self._poster_generation = None
        # Deferred: the list and model this reads are built later in setup_ui.
        QTimer.singleShot(0, self._sync_search_posters)

    def _toggle_search_posters(self) -> None:
        self.config.search_view_posters = not self.config.search_view_posters
        _cfgsave.save_soon(self)
        self._sync_search_posters()

    def _sync_search_posters(self) -> None:
        """Make the buttons and grid match ``config.search_view_posters``."""
        on = bool(self.config.search_view_posters)
        self._posters_btn.setText("List" if on else "Posters")
        self._posters_btn.setToolTip(
            "Show these results as a list" if on else "Show these results as posters")
        _icon_utils.set_button_icon(self._posters_btn, "as_list" if on else "as_grid")
        self._poster_zoom.setVisible(on)
        self._shelf_btn.setVisible(on)
        if on:
            self._ensure_poster_grid()
            self._refresh_poster_grid()
        self._sync_poster_grid_visibility()

    def _ensure_poster_grid(self) -> None:
        if "_poster_grid" in self.__dict__:
            return
        grid = _BrowseView(self.image_cache, self.config, self.channels_list)
        grid.set_embedded(self._build_poster_band)
        grid.setAutoFillBackground(True)
        grid.setGeometry(self.channels_list.rect())
        self.channels_list.installEventFilter(_CoverParent(grid))
        grid.cardClicked.connect(self.show_channel_details_by_id)
        grid.cardDoubleClicked.connect(self.play_channel_by_id)
        grid.cardMiddleClicked.connect(self._dispatch_middle_click)
        grid.cardContextMenu.connect(self._on_rec_channel_context_menu)
        grid.loadMoreRequested.connect(self.channel_model.fetchMore)
        self.discover_view.zoomChanged.connect(self._on_poster_zoom_changed)
        model = self.channel_model
        for signal in (model.modelReset, model.rowsInserted, model.rowsRemoved,
                       model.layoutChanged, model.dataChanged):
            signal.connect(self._schedule_poster_refresh)
        # Other views reuse the list without Search's controls, and keep rows.
        self.search_controls.installEventFilter(
            _ShowHideWatcher(grid, self._sync_poster_grid_visibility))
        self._poster_grid = grid

    def _sync_poster_grid_visibility(self) -> None:
        grid = self.__dict__.get("_poster_grid")
        if grid is not None:
            grid.setVisible(bool(self.config.search_view_posters)
                            and not self.search_controls.isHidden()
                            and self.channel_model.rowCount() > 0)

    def _schedule_poster_refresh(self, *_args) -> None:
        if self.config.search_view_posters:
            self._poster_refresh_timer.start()

    def _refresh_poster_grid(self) -> None:
        """Redraw the grid from the model's rows; new results go back to the top."""
        model = self.channel_model
        cards: list = []
        bands: list = []
        for row, kind, channel in model.display_rows():
            if kind == "channel":
                cards.append(card_from_list_row(channel))
            else:
                bands.append((len(cards), (row, kind), self._poster_band_height(kind)))
        generation = model.generation
        self._poster_grid.show_rows(
            cards, bands, keep_scroll=generation == self._poster_generation)
        self._poster_generation = generation
        self._poster_grid.set_has_more(model.canFetchMore())
        self._sync_poster_grid_visibility()
        self._sync_shelf_btn()

    def _poster_band_height(self, kind: str) -> int:
        font = self._poster_grid.font()
        if kind == "header":
            return _band.band_height(font)
        return self._poster_grid.fontMetrics().height() + _PERSON_BAND_PAD_V

    def _build_poster_band(self, payload) -> _PosterBand:
        row, kind = payload
        band = _PosterBand(self.channel_model, row, kind)
        band.clicked.connect(self._on_channel_list_clicked)
        band.modeToggled.connect(self._on_section_mode_toggled)
        return band

    def _apply_poster_zoom(self) -> None:
        self.discover_view.set_zoom(self._poster_zoom.value() / 100.0)

    def _on_poster_zoom_changed(self) -> None:
        self._poster_zoom.blockSignals(True)
        self._poster_zoom.setValue(round(self.config.discover_zoom * 100))
        self._poster_zoom.blockSignals(False)
        self._poster_grid.apply_zoom()

    # ── Keeping the results ───────────────────────────────────────────────

    def _current_shelf_target(self) -> "ShelfTarget | None":
        """Read Search's state on the main thread and resolve it."""
        state = self.current_filter_state or self.filter_panel.get_filter_state()
        category = self._details_category_filter or ""
        collection = ""
        if category:
            collection = next((c.detected_collection or "" for _r, kind, c
                               in self.channel_model.display_rows() if kind == "channel"), "")
        return resolve_shelf_target(
            search=self.search_input.text(),
            category=category,
            collection=collection,
            genre=self._details_genre_filter or "",
            person=self._details_person_filter or "",
            tag=self._details_tag_filter,
            tag_includes=state.get("tag_includes"),
            tag_excludes=state.get("tag_excludes"),
        )

    def _sync_shelf_btn(self) -> None:
        """Say what the button would do, and whether it is already done."""
        target = None if self._list_scope != "all" else self._current_shelf_target()
        btn = self._shelf_btn
        done, label, role = False, "Save as shelf", "recipe"
        tip = "Search or filter first: everything at once is not a shelf"
        if target is not None and target.key:
            done = target.key in self.config.discover_pinned_shelves
            label, role = ("Pinned" if done else "Pin as shelf"), "pin"
            tip = (f"Pin the {target.name} shelf to Discover. "
                   "It can hold more than this list if the name covers several categories.")
        elif target is not None:
            done = any(isinstance(r, dict) and r.get("name") == target.name
                       for r in self.config.saved_recipes)
            label = "Saved" if done else label
            tip = f"Keep {target.name} as a Discover shelf that updates as your library changes"
        btn.setText(label)
        _icon_utils.set_button_icon(btn, role)
        btn.setToolTip(tip)
        btn.setEnabled(target is not None and not done)

    def _open_saved_search(self, entry: dict) -> None:
        """Open a saved search in Search, the only place that can show its words."""
        self._reset_context_filters()
        self._set_search_text_silently(entry.get("search") or "")
        if entry.get("category"):
            self._on_category_filter_requested(entry["category"])
            return
        self.switch_to_list_view()
        self.load_channels()

    def _on_shelf_btn_clicked(self) -> None:
        target = self._current_shelf_target()
        if target is None:
            return
        if target.key:
            self.discover_view.pin_shelf(target.key)
            self.status(f"Pinned {target.name} to Discover")
        else:
            entry = _RecipeSavedMixin._recipe_to_config(
                target.includes, target.excludes, target.name,
                search=target.search, category=target.category)
            self.config.saved_recipes = [*self.config.saved_recipes, entry]
            _cfgsave.save_soon(self)
            self.recipe_view._load_saved_recipes()
            self.discover_view.pin_shelf(f"{_RECIPE_PREFIX}{target.name}")
            self.discover_view.reload()
            self.status(f"Saved {target.name} as a Discover shelf")
            logger.info("Saved search as shelf: {!r}", target.name)
        self._sync_shelf_btn()
