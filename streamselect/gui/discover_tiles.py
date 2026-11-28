"""A collapsed Discover shelf as a tile (design "Discover's Collapsed Shelves", A).

A collapsed shelf used to be one line with its name: forty-eight of them took a
column of the page and left the rest empty. Each is now a card with its four
newest posters (hover one for its title), its name and its title count, laid out
in a grid whose column count follows the width, cards stretched to fill each row.
Clicking a tile opens the shelf as a row where the tile was (``discover_groups``);
pin and hide show on hover, as on a row.

Posters and counts come from ``core/shelf_preview.py``, asked for only for tiles
on screen (``DiscoverTilesMixin``), one background fetch at a time.
"""

from __future__ import annotations

import weakref

from PyQt6.QtCore import QObject, QRect, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from streamselect.gui import cursor_affordance
from streamselect.gui import icon_utils as _icon_utils
from streamselect.gui import theme as _theme

TILE_MIN_W = 250          # at zoom 1.0; scaled by the Discover card zoom
TILE_GAP = 12
_POSTERS = 4


def _fmt_count(n: int | None) -> str:
    if n is None:
        return ""
    return f"{n / 1000:.1f}k titles" if n >= 1000 else f"{n} title{'s' if n != 1 else ''}"


class _PosterSlot(QLabel):
    """One poster on a tile; its title on hover."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._url = ""
        self._poster: QPixmap | None = None      # the loaded image, kept to re-fit on resize
        _theme.style_fn(self, lambda: f"background: {_theme.COLOR_BG_DEEP}; border-radius: 3px;")

    def show_card(self, card, image_cache) -> None:
        url = (card.thumbnail_url or "") if card else ""
        if url and url == self._url and self._poster is not None:
            self._fit()                          # same poster: re-fit, never reload (owner report)
            return
        self.setToolTip(card.title if card else "")
        self._url, self._poster = url, None
        self.clear()
        if self._url and image_cache is not None:
            image_cache.subscribe(self._url, self._on_loaded)       # bound method: held weakly
            image_cache.get_image_async(self._url)

    def _on_loaded(self, url: str, pixmap: QPixmap) -> None:
        if url != self._url or pixmap.isNull():
            return
        self._poster = pixmap
        self._fit()

    def _fit(self) -> None:
        """Crop the kept poster to fill this slot's current size."""
        scaled = self._poster.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                     Qt.TransformationMode.SmoothTransformation)
        x, y = (scaled.width() - self.width()) // 2, (scaled.height() - self.height()) // 3
        self.setPixmap(scaled.copy(QRect(max(0, x), max(0, y), self.width(), self.height())))


class ShelfTile(QFrame):
    """A collapsed shelf: four posters, its name and size; a click opens it."""

    def __init__(self, shelf, image_cache) -> None:
        super().__init__()
        self.setObjectName("shelfTile")
        self._shelf = weakref.ref(shelf)
        self.shelf_key = shelf._shelf_key
        self._image_cache = image_cache
        self.has_preview = False
        self._cards: list = []
        _theme.style_fn(self, lambda: f"#shelfTile {{ background: {_theme.OVERLAY_08}; border-radius: 8px; }}"
                                      f"#shelfTile:hover {{ background: {_theme.OVERLAY_15}; }}")
        cursor_affordance.set_clickable(self)
        self.setToolTip(f"Expand {shelf._title}")
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 8)
        v.setSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.slots = [_PosterSlot() for _ in range(_POSTERS)]
        for s in self.slots:
            row.addWidget(s)
        row.addStretch(1)
        v.addLayout(row)
        text = QHBoxLayout()
        # Semi-bold, a size up, in the bright text colour: a regular-weight name was
        # lost among four posters (owner report).
        self.name_lbl = QLabel(shelf._title)
        self.name_lbl.setTextFormat(Qt.TextFormat.PlainText)
        _theme.style_fn(self.name_lbl, lambda: f"font-size: {_theme.FONT_LG}; font-weight: 600;"
                                               f" color: {_theme.COLOR_TEXT_HI};")
        self.count_lbl = QLabel(" ".join(shelf.chips))
        _theme.style(self.count_lbl, "TEXT_SM_MUTED")
        text.addWidget(self.name_lbl, 1)
        text.addWidget(self.count_lbl)
        v.addLayout(text)
        # Pin and hide, as on a row: shown on hover, over the first poster's corner.
        self.pin_btn = _icon_utils.icon_button("pin", "Pin to top", style="DISCOVER_SHELF_PAGE_BTN",
                                               px=12, parent=self)
        self.hide_btn = _icon_utils.icon_button("hide", "Hide this shelf", style="DISCOVER_SHELF_PAGE_BTN",
                                                px=12, parent=self)
        for b in (self.pin_btn, self.hide_btn):
            b.setFixedSize(24, 22)
            b.hide()
        self.pin_btn.clicked.connect(lambda: (s := self._shelf()) and s._on_pin_clicked())
        self.hide_btn.clicked.connect(lambda: (s := self._shelf()) and s.hideRequested.emit(self.shelf_key))

    def set_width(self, w: int) -> None:
        """Size the tile and its posters for a column *w* px wide (a no-op at its width)."""
        if w == self.width() and self.minimumWidth() == w:
            return
        pw = max(30, (w - 20 - (_POSTERS - 1) * 4) // _POSTERS)
        for s in self.slots:
            s.setFixedSize(pw, int(pw * 1.5))
        self.setFixedSize(w, 10 + int(pw * 1.5) + 6 + 24 + 8)
        self.hide_btn.move(w - 30, 6)
        self.pin_btn.move(w - 58, 6)
        if self._cards:
            self._fill()

    def set_preview(self, cards: list, count: int | None) -> None:
        """Show the shelf's posters and size (from ``shelf_preview``)."""
        self.has_preview = True
        self._cards = list(cards)[:_POSTERS]
        s = self._shelf()
        chips = " ".join(s.chips) if s is not None else ""
        self.count_lbl.setText("  ".join(t for t in (_fmt_count(count), chips) if t))
        self._fill()

    def _fill(self) -> None:
        for slot, card in zip(self.slots, self._cards + [None] * _POSTERS):
            slot.show_card(card, self._image_cache)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.button() == Qt.MouseButton.LeftButton and (s := self._shelf()) is not None:
            s.expandRequested.emit(self.shelf_key)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if (s := self._shelf()) is not None:
            s.menuRequested.emit(self.shelf_key, event.globalPos())
        event.accept()

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt naming
        for b in (self.pin_btn, self.hide_btn):
            b.show()
            b.raise_()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt naming
        for b in (self.pin_btn, self.hide_btn):
            b.hide()
        super().leaveEvent(event)


class TileGrid(QWidget):
    """Tiles in rows: as many columns as fit, each tile stretched to fill its row."""

    def __init__(self, zoom: float = 1.0) -> None:
        super().__init__()
        self._tiles: list[ShelfTile] = []
        self._min_w = int(TILE_MIN_W * max(0.6, min(1.8, zoom)))

    def add(self, tile: ShelfTile) -> None:
        tile.setParent(self)
        self._tiles.append(tile)

    def tiles(self) -> list[ShelfTile]:
        return list(self._tiles)

    def arrange(self) -> None:
        shown = [t for t in self._tiles if not t.isHidden()]
        w = max(self.width(), self._min_w)
        cols = max(1, (w + TILE_GAP) // (self._min_w + TILE_GAP))
        tw = (w - (cols - 1) * TILE_GAP) // cols
        y = th = 0
        for i, t in enumerate(shown):
            t.set_width(tw)
            th = t.height()
            t.move((i % cols) * (tw + TILE_GAP), (i // cols) * (th + TILE_GAP))
        rows = (len(shown) + cols - 1) // cols
        y = rows * th + max(0, rows - 1) * TILE_GAP
        if self.height() != y:
            self.setFixedHeight(y)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().resizeEvent(event)
        self.arrange()


class _PreviewWorker(QObject):
    """Fetch tile previews for a batch of shelf keys, one after another."""

    ready = pyqtSignal(str, list, object)   # (shelf_key, cards, count | None)
    done = pyqtSignal()

    def __init__(self, db, config, keys: list[str]) -> None:
        super().__init__()
        self._db, self._config, self._keys = db, config, list(keys)
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        from streamselect.core.shelf_preview import shelf_preview
        from streamselect.gui.discover_workers import scope_kwargs
        try:
            with self._db.session_scope(commit=False) as session:
                fk, af, ek = scope_kwargs(session, self._config)
                for key in self._keys:
                    if self._cancelled:
                        return
                    try:
                        cards, count = shelf_preview(session, self._config, key, fk=fk, af=af, ek=ek)
                    except Exception:
                        from loguru import logger
                        logger.exception("Tile preview failed for {}", key)
                        cards, count = [], None
                    if not self._cancelled:
                        self.ready.emit(key, cards, count)
        finally:
            self.done.emit()


class DiscoverTilesMixin:
    """DiscoverView's tile previews: fetched for the tiles on screen, as they appear."""

    def _init_tiles(self, page_scroll) -> None:
        self._preview_thread: QThread | None = None
        self._preview_worker: _PreviewWorker | None = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._request_previews)
        page_scroll.verticalScrollBar().valueChanged.connect(self._previews_soon)   # bound: no strong ref

    def _previews_soon(self, *_args) -> None:
        self._preview_timer.start(150)

    def _tiles_on_screen(self) -> list[ShelfTile]:
        out = []
        for shelf in self._shelf_widgets.values():
            t = getattr(shelf, "tile", None)
            if t is not None and not t.has_preview and t.isVisible() and not t.visibleRegion().isEmpty():
                out.append(t)
        return out

    def _request_previews(self) -> None:
        """Start one background fetch for the on-screen tiles that have no posters yet."""
        if self._preview_thread is not None and self._preview_thread.isRunning():
            self._preview_timer.start(300)          # after the current batch
            return
        keys = [t.shelf_key for t in self._tiles_on_screen()]
        if not keys or not self._active:
            return
        self._preview_thread = QThread()
        self._preview_worker = _PreviewWorker(self._db, self._config, keys)
        self._preview_worker.moveToThread(self._preview_thread)
        self._preview_thread.started.connect(self._preview_worker.run)
        self._preview_worker.ready.connect(self._on_preview_ready)
        self._preview_worker.done.connect(self._preview_thread.quit)
        self._preview_worker.done.connect(self._previews_soon)          # tiles that scrolled in meanwhile
        self._preview_thread.start()

    def _on_preview_ready(self, shelf_key: str, cards: list, count) -> None:
        shelf = self._shelf_widgets.get(shelf_key)
        tile = getattr(shelf, "tile", None) if shelf is not None else None
        if tile is not None:
            tile.set_preview(cards, count)

    def _stop_previews(self) -> None:
        self._stop_loader(self.__dict__.get("_preview_worker"), self.__dict__.get("_preview_thread"))
