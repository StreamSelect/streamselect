"""Discover's groups (design "Discover as Your Dashboard", rev 2).

The page reads top to bottom as six groups: what you pinned, your shelves, Discover's
own shelves, every genre, the years and decades, the provider's categories. A
shelf's zone (pinned / expanded / collapsed, ``discover_workers.determine_zone``)
is its STATE; the group is its PLACE. Opening or collapsing a shelf leaves it where
it is; pinning lifts it into Pinned, unpinning puts it back in its group.

Inside a group the shelves keep the order the loader sent them in; Pinned follows
the order of ``discover_pinned_shelves``, so the Manage dialog's Up / Down orders it.
Every group but Pinned collapses as a whole from its heading, which states the
count; the choice is remembered. Shelves behave the same in every group.
"""

from __future__ import annotations

import weakref
from bisect import bisect_right

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from streamselect.gui import deferred_config_save as _cfgsave
from streamselect.gui import icon_utils as _icon_utils
from streamselect.gui import theme as _theme
from streamselect.gui.discover_shelf import more_categories_row
from streamselect.gui.discover_tiles import TileGrid
from streamselect.gui.discover_workers import (
    _COLLECTION_PREFIX, _DECADE_PREFIX, _GENRE_PREFIX, _RECIPE_PREFIX, _USER_CAT_PREFIX, _YEAR_PREFIX,
    WATCH_LATER,
)

PINNED, LISTS, APP, GENRES, DECADES, CATEGORIES = (
    "pinned", "lists", "app", "genres", "decades", "categories")

#: (group, heading), top to bottom. All but Pinned fold from a button heading.
GROUPS: tuple[tuple[str, str], ...] = (
    (PINNED, "Pinned"), (LISTS, "Your Shelves"), (APP, "Discover's Shelves"),
    (GENRES, "Genres"), (DECADES, "Decades"), (CATEGORIES, "Provider Categories"),
)
FOLDABLE = (LISTS, APP, GENRES, DECADES, CATEGORIES)

#: Open on a profile's first visit (the loader's first-launch defaults): your shelves
#: and Recently Added, the one shelf of Discover's own that changes daily.
DEFAULT_EXPANDED = frozenset({f"{_USER_CAT_PREFIX}{WATCH_LATER}", "recommended", "queue", "recently_added"})


def group_of(shelf_key: str) -> str:
    """The group a shelf lives in when it isn't pinned."""
    if shelf_key in ("recommended", "queue") or shelf_key.startswith((_USER_CAT_PREFIX, _RECIPE_PREFIX)):
        return LISTS
    if shelf_key.startswith(_GENRE_PREFIX):
        return GENRES
    if shelf_key.startswith((_YEAR_PREFIX, _DECADE_PREFIX)):
        return DECADES
    if shelf_key.startswith(_COLLECTION_PREFIX):
        return CATEGORIES
    return APP


def seed_dashboard_defaults(config) -> None:
    """Open your shelves once on a profile that already had a Discover layout.

    A new profile gets :data:`DEFAULT_EXPANDED` from the first-launch rule; a
    returning one has its zones recorded, and an unrecorded key reads as collapsed,
    so without this the new defaults would never reach it. Runs once; a shelf the
    user pinned or hid keeps that.
    """
    if config.discover_dashboard_seeded:
        return
    if config.discover_zones_seeded:
        taken = {*config.discover_pinned_shelves, *config.discover_hidden_shelves,
                 *config.discover_expanded_shelves}
        config.discover_expanded_shelves = [*config.discover_expanded_shelves, *(
            k for k in ("recommended", "queue", f"{_USER_CAT_PREFIX}{WATCH_LATER}") if k not in taken)]
    config.discover_dashboard_seeded = True
    config.save()


def style_group_button(btn: QPushButton) -> None:
    """The look of a foldable group's heading: a full-width tinted bar."""
    btn.setFixedHeight(36)
    _theme.style_fn(btn, lambda: "QPushButton {"
                    f"  background: {_theme.OVERLAY_08}; border: none; border-radius: 4px;"
                    f"  color: {_theme.COLOR_TEXT_HI}; font-size: {_theme.FONT_LG};"
                    "  text-align: left; padding: 0 12px; }"
                    f"QPushButton:hover {{ background: {_theme.OVERLAY_15}; color: {_theme.COLOR_TEXT_HI}; }}")


class ShelfGroup(QWidget):
    """One group: a heading over its shelves, kept in rank order.

    An open shelf is a row; each run of collapsed shelves is one grid of tiles
    (``discover_tiles``), so a tile opened in place splits its grid around the row.
    """

    relaid = pyqtSignal()           # after a layout pass: new tiles may be on screen

    def __init__(self, key: str, heading: QWidget, zoom: float = 1.0) -> None:
        super().__init__()
        self.key = key
        self.heading = heading
        self._zoom = zoom
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 6, 0, 0)
        v.setSpacing(4)
        v.addWidget(heading)
        self.body = QWidget()
        self.shelves = QVBoxLayout(self.body)
        self.shelves.setContentsMargins(0, 0, 0, 0)
        self.shelves.setSpacing(6)
        v.addWidget(self.body)
        self._entries: list[tuple[float, QWidget]] = []
        self._grids: list[TileGrid] = []
        self._soon = QTimer(self)
        self._soon.setSingleShot(True)
        self._soon.timeout.connect(self.relayout)
        # Never taller than its content: a window taller than the page leaves the
        # spare height below the last section, not spread between its rows.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.setVisible(False)

    def count(self) -> int:
        return len(self._entries)

    def insert(self, shelf: QWidget, rank: float) -> None:
        i = bisect_right([r for r, _ in self._entries], rank)
        self._entries.insert(i, (rank, shelf))
        shelf.setParent(self.body)
        shelf.collapsedChanged.connect(self.relayout_soon)
        self.relayout_soon()

    def remove(self, shelf: QWidget) -> None:
        for i, (_, s) in enumerate(self._entries):
            if s is shelf:
                del self._entries[i]
                shelf.collapsedChanged.disconnect(self.relayout_soon)
                self.shelves.removeWidget(shelf)
                tile = getattr(shelf, "tile", None)
                if tile is not None and tile.parent() in self._grids:
                    self._park(tile)                # before its grid goes; the next group adopts it
                self.relayout_soon()
                return

    def members(self) -> list[QWidget]:
        return [s for _, s in self._entries]

    def clear(self) -> None:
        for _, w in self._entries:
            w.cancel_pending_build()      # PERF-17: stop any in-flight chunked card build
            w.deleteLater()
        self._entries.clear()
        self.relayout()

    def _park(self, tile: QWidget) -> None:
        """Keep a tile that is not in a grid (its shelf is open, or moving) alive and hidden."""
        tile.hide()
        tile.setParent(self.body)

    def relayout_soon(self) -> None:
        self._soon.start(0)

    def relayout(self) -> None:
        """Rows for open shelves, a tile grid for each run of collapsed ones."""
        while self.shelves.count():
            self.shelves.takeAt(0)
        old, self._grids, grid = self._grids, [], None
        for _, shelf in self._entries:
            tile = getattr(shelf, "tile", None)
            shown = getattr(shelf, "matches_filter", True)
            if shelf._collapsed and tile is not None:
                if grid is None:
                    grid = TileGrid(self._zoom)
                    self.shelves.addWidget(grid)
                    self._grids.append(grid)
                grid.add(tile)
                tile.setVisible(shown)
                shelf.hide()
            else:
                grid = None
                self.shelves.addWidget(shelf)
                shelf.setVisible(shown)
        for g in old:
            for t in g.tiles():
                if t.parent() is g:       # an opened shelf's tile: kept, out of sight
                    self._park(t)
            g.deleteLater()
        for g in self._grids:
            g.arrange()
        self.relaid.emit()


def _toggler(view, key: str):
    """A heading's click: folds *key* without the connection keeping the view alive."""
    ref = weakref.ref(view)

    def toggle(_checked: bool = False) -> None:
        if (v := ref()) is not None:
            v._toggle_group(key)
    return toggle


class DiscoverGroupsMixin:
    """DiscoverView's placement: which group a shelf sits in, and the headings."""

    def _build_groups(self, into: QVBoxLayout) -> None:
        self._groups: dict[str, ShelfGroup] = {}
        self._arrival: dict[str, int] = {}
        for key, text in GROUPS:
            if key == CATEGORIES:
                self._more_btn = QPushButton(text)
                head = more_categories_row(self)
            elif key in FOLDABLE:
                head = QPushButton(text)
            else:
                head = QLabel(text.upper())
                _theme.style(head, "TEXT_SM_MUTED")
                head.setContentsMargins(4, 4, 0, 0)
            btn = self._more_btn if key == CATEGORIES else head
            if key in FOLDABLE:
                style_group_button(btn)
                btn.clicked.connect(_toggler(self, key))
            self._groups[key] = ShelfGroup(key, head, self._config.discover_zoom)
            self._groups[key].relaid.connect(self._previews_soon)
            self._groups[key].label = text
            into.addWidget(self._groups[key])

    def _group_is_open(self, key: str) -> bool:
        if key == CATEGORIES:
            return bool(self._config.discover_more_expanded)
        return key not in self._config.discover_folded_groups

    def _toggle_group(self, key: str) -> None:
        cfg = self._config
        if key == CATEGORIES:
            cfg.discover_more_expanded = not cfg.discover_more_expanded
        elif key in cfg.discover_folded_groups:
            cfg.discover_folded_groups = [k for k in cfg.discover_folded_groups if k != key]
        else:
            cfg.discover_folded_groups = [*cfg.discover_folded_groups, key]
        _cfgsave.save_soon(self)
        self._update_group_heads()
        self._previews_soon()                    # an opened group's tiles may now be on screen

    def _place_of(self, shelf_key: str, zone: str) -> tuple[ShelfGroup, float]:
        """The group *shelf_key* goes in for *zone*, and its rank there."""
        arrival = self._arrival.setdefault(shelf_key, len(self._arrival))
        if zone == "pinned":
            pins = self._config.discover_pinned_shelves
            return self._groups[PINNED], (pins.index(shelf_key) if shelf_key in pins else 10_000 + arrival)
        # Open shelves lead their group when it is laid out (a load, or a move into
        # it); one opened from its tile stays in place until then (_move_shelf).
        return self._groups[group_of(shelf_key)], arrival + (1_000_000 if zone == "collapsed" else 0)

    def _add_to_zone(self, shelf, zone: str) -> None:
        group, rank = self._place_of(shelf._shelf_key, zone)
        group.insert(shelf, rank)
        self._update_group_heads()

    def _remove_from_zone(self, shelf, zone: str) -> None:
        self._place_of(shelf._shelf_key, zone)[0].remove(shelf)
        self._update_group_heads()

    def _update_group_heads(self) -> None:
        """Each group shows when it holds something; a foldable heading states its count.

        The count includes collapsed strips still buffered (D2 deferral), so the
        heading is right while the load streams in. Provider Categories always shows
        once loaded: its heading carries the Live categories switch.
        """
        pending: dict[str, int] = {}
        for d in self._pending_collapsed:
            pending[group_of(d.shelf_key)] = pending.get(group_of(d.shelf_key), 0) + 1
        for key, group in self._groups.items():
            n = group.count() + pending.get(key, 0)
            group.setVisible(n > 0 or (key == CATEGORIES and self._loaded))
            if key not in FOLDABLE:
                group.body.setVisible(True)      # the shelf filter may have hidden it
                continue
            is_open = self._group_is_open(key)
            btn = self._more_btn if key == CATEGORIES else group.heading
            btn.setText(f"{group.label}  ({n})")
            _icon_utils.set_button_icon(btn, "collapse" if is_open else "expand")
            btn.setToolTip(f"{'Collapse' if is_open else 'Expand'} {group.label} ({n} shelves)")
            group.body.setVisible(is_open)

    def _apply_zone_config(self, hidden_before: set[str]) -> None:
        """Bring the page in line with the zone lists, shelf by shelf (after Manage).

        Each shelf moves, opens, collapses or goes, in place; nothing is rebuilt.
        Only a shelf restored from hidden has no widget to move, so that one case
        reloads. Ends by saving the lists from what is on screen.
        """
        cfg = self._config
        if set(hidden_before) - set(cfg.discover_hidden_shelves):
            self.refresh()
            return
        pinned, expanded = list(cfg.discover_pinned_shelves), set(cfg.discover_expanded_shelves)
        hidden = set(cfg.discover_hidden_shelves)
        for key in list(self._shelf_widgets):
            if key in hidden:
                self._on_hide_requested(key)
                continue
            zone = "pinned" if key in pinned else "expanded" if key in expanded else "collapsed"
            shelf = self._shelf_widgets[key]
            if zone == self._shelf_zones.get(key) == "pinned":       # re-rank: Up / Down
                self._remove_from_zone(shelf, zone)
                self._add_to_zone(shelf, zone)
            else:
                self._move_shelf(key, zone)
            if zone != "collapsed" and key not in self._loaded_shelf_keys:
                self._start_expand_fetch(key)
        self._save_zone_config()

    def _show_filter_matches(self, wanted: dict) -> None:
        """While the shelf filter has text: only groups with a match show, opened."""
        for group in self._groups.values():
            hit = any(wanted.get(w, False) for w in group.members())
            group.setVisible(hit)
            group.body.setVisible(hit)
