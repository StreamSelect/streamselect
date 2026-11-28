"""Discover's groups (design "Discover as Your Dashboard", rev 2).

The page reads top to bottom as six groups: what you pinned, your lists, Discover's
own shelves, every genre, the years and decades, the provider's categories. A
shelf's zone (pinned / expanded / collapsed, ``discover_workers.determine_zone``)
is its STATE; the group is its PLACE. Opening or collapsing a shelf leaves it where
it is; pinning lifts it into Pinned, unpinning puts it back in its group.

Inside a group the shelves keep the order the loader sent them in; Pinned follows
the order of ``discover_pinned_shelves``, so the Manage dialog's Up / Down orders it.
Genres, Decades and the provider categories collapse as a whole from their heading,
which states the count; the choice is remembered.
"""

from __future__ import annotations

import weakref
from bisect import bisect_right

from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from streamselect.gui import deferred_config_save as _cfgsave
from streamselect.gui import icon_utils as _icon_utils
from streamselect.gui import theme as _theme
from streamselect.gui.discover_shelf import more_categories_row
from streamselect.gui.discover_workers import (
    _COLLECTION_PREFIX, _DECADE_PREFIX, _GENRE_PREFIX, _RECIPE_PREFIX, _USER_CAT_PREFIX, _YEAR_PREFIX,
    WATCH_LATER,
)

PINNED, LISTS, APP, GENRES, DECADES, CATEGORIES = (
    "pinned", "lists", "app", "genres", "decades", "categories")

#: (group, heading), top to bottom. The last three fold from a button heading.
GROUPS: tuple[tuple[str, str], ...] = (
    (PINNED, "Pinned"), (LISTS, "Your lists"), (APP, "Discover's shelves"),
    (GENRES, "Genres"), (DECADES, "Decades"), (CATEGORIES, "Provider Categories"),
)
FOLDABLE = (GENRES, DECADES, CATEGORIES)

#: Open on a profile's first visit (the loader's first-launch defaults): your lists
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
    """Open your lists once on a profile that already had a Discover layout.

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
    """One group: a heading over its shelves, kept in rank order."""

    def __init__(self, key: str, heading: QWidget) -> None:
        super().__init__()
        self.key = key
        self.heading = heading
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 6, 0, 0)
        v.setSpacing(4)
        v.addWidget(heading)
        self.body = QWidget()
        self.shelves = QVBoxLayout(self.body)
        self.shelves.setContentsMargins(0, 0, 0, 0)
        self.shelves.setSpacing(6)
        v.addWidget(self.body)
        self._ranks: list[float] = []
        self.setVisible(False)

    def count(self) -> int:
        return len(self._ranks)

    def insert(self, shelf: QWidget, rank: float) -> None:
        i = bisect_right(self._ranks, rank)
        self._ranks.insert(i, rank)
        self.shelves.insertWidget(i, shelf)

    def remove(self, shelf: QWidget) -> None:
        i = self.shelves.indexOf(shelf)
        if i >= 0:
            self.shelves.removeWidget(shelf)
            del self._ranks[i]

    def members(self) -> list[QWidget]:
        return [self.shelves.itemAt(i).widget() for i in range(self.shelves.count())]

    def clear(self) -> None:
        for w in self.members():
            self.shelves.removeWidget(w)
            w.cancel_pending_build()      # PERF-17: stop any in-flight chunked card build
            w.deleteLater()
        self._ranks.clear()


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
            self._groups[key] = ShelfGroup(key, head)
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

    def _place_of(self, shelf_key: str, zone: str) -> tuple[ShelfGroup, float]:
        """The group *shelf_key* goes in for *zone*, and its rank there."""
        arrival = self._arrival.setdefault(shelf_key, len(self._arrival))
        if zone == "pinned":
            pins = self._config.discover_pinned_shelves
            return self._groups[PINNED], (pins.index(shelf_key) if shelf_key in pins else 10_000 + arrival)
        return self._groups[group_of(shelf_key)], arrival

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

    def _show_filter_matches(self, wanted: dict) -> None:
        """While the shelf filter has text: only groups with a match show, opened."""
        for group in self._groups.values():
            hit = any(wanted.get(w, False) for w in group.members())
            group.setVisible(hit)
            group.body.setVisible(hit)
