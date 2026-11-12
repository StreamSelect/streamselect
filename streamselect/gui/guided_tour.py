"""The guided tour: spotlight the real controls, one at a time, with a sentence each.

A user (Q10/R8; revised): a short tour that opens on a theme picker
(tour_theme_picker), then search, what each kind of row
plays, the top bar, Exclusions, the sidebar's lists and Sources, re-runnable, and the user
is told where it lives when it ends. It is offered once, when a new source
finishes its first load — before that every view is empty and the tour would
point at controls with nothing in them — and always from Tools ▸ Take the tour.

Explore is NOT a stop: on a new install every list is empty and there is
nothing to point at. It is a just-in-time tip instead (``just_in_time_tips``),
shown the first time a list has something in it. A tip is this same overlay
with one card and "Got it" (``TourOverlay(tip=True)``).

A stop highlights the live widget (never a picture of one): the window is
dimmed except for a ring around the control, and a callout card explains it
with Back / Next / End tour. A stop whose control is not on screen (the sidebar
collapsed, say) still shows its card, centred, rather than pointing at nothing.
Esc ends the tour; ← and → step through it.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PyQt6.QtCore import QEvent, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget,
)

from streamselect.gui import theme as _theme
from streamselect.gui.token_color import to_qcolor


@dataclass(frozen=True)
class TourStop:
    """One stop: what to say, and how to find the control on the host."""

    title: str
    body: str
    target: Callable[[object], QWidget | None]
    #: Ring what the control DRAWS, not its whole box — for a widget a layout
    #: stretches far past its content (the Sources line fills the sidebar's
    #: spare height, so its box is ~440 px of empty space).
    tight: bool = False
    #: Icon rows shown under the body: (icon role, what it means). Each is the
    #: same mark the control draws, so the card can be read against the screen.
    legend: tuple[tuple[str, str], ...] = ()
    #: Ring only this part of the target (the Style entry of the menu bar).
    area: Callable[[QWidget], QRect] | None = None
    #: Keep the card in the middle of the window even when something is ringed.
    centred: bool = False
    #: Show the theme list (tour_theme_picker) on this card.
    themes: bool = False


def _attr(name: str) -> Callable[[object], QWidget | None]:
    # __dict__.get: the host is a MainWindow, where a missing attribute raises
    # RuntimeError through Qt rather than returning a default (the project rules).
    return lambda host: host.__dict__.get(name)


def _menu_bar(host: object) -> QWidget | None:
    return host.menuBar() if isinstance(host, QMainWindow) else None


def _style_entry(menu_bar: QWidget) -> QRect:
    """Where the menu bar draws its Style entry (empty: not found)."""
    for action in menu_bar.actions():
        if action.text().replace("&", "") == "Style":
            return menu_bar.actionGeometry(action)
    return QRect()


#: The stops, in order.
TOUR_STOPS: tuple[TourStop, ...] = (
    TourStop("Pick a look",
             "Click a theme to switch to it now. You can change it any time "
             "from Style ▸ Theme in the menu bar.",
             _menu_bar, area=_style_entry, centred=True, themes=True),
    TourStop("Search",
             "Search every source at once: titles, channels and categories. "
             "Type, then press Enter.",
             _attr("search_input")),
    TourStop("What each row is",
             "The mark at the start of a row says what playing it does.",
             _attr("channels_list"),
             legend=(("live", "Live channel: joins the broadcast already in "
                              "progress, like turning on a TV."),
                     ("movie", "Movie: on demand, starts from the beginning."),
                     ("series", "Series: on demand; pick an episode and it "
                                "starts from the beginning."))),
    TourStop("The top bar",
             "Switch views here: Search, EPG (the TV guide), Recommended, "
             "Discover and Recipe. The lit one is where you are.",
             _attr("_nav_track")),
    TourStop("Exclusions",
             "Hide what you never want to see — regions, languages, "
             "categories, keywords — everywhere at once. Click to turn it on "
             "or off; right-click to change what it hides.",
             _attr("_filter_chip")),
    TourStop("Your lists",
             "Watch Alerts, Recommended, Watch Queue, Favorites and History. "
             "They fill up as you watch, save and rate.",
             _attr("sidebar_splitter")),
    TourStop("Sources",
             "Where everything comes from. Click here to add, edit or refresh "
             "a source; this line warns you when one is turned off or about "
             "to expire.",
             _attr("sources_strip"), tight=True),
)

#: Where the tour lives — said in the menu entry and when the tour ends.
TOUR_MENU_PATH = "Tools ▸ Take the tour"

def _drawn_rect(widget: QWidget) -> QRect:
    """Where *widget*'s children actually draw: each child's preferred height
    around its own centre (a stretched label paints its text there, not over
    its whole box). Falls back to the widget's rect when it has none."""
    area = QRect()
    for child in widget.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly):
        if not child.isVisible():
            continue
        g = child.geometry()
        hint = (child.heightForWidth(g.width()) if child.hasHeightForWidth()
                else child.sizeHint().height())      # a wrapped label: its real lines
        h = min(g.height(), max(hint, 1))
        area = area.united(QRect(g.x(), g.center().y() - h // 2, g.width(), h))
    return area if not area.isEmpty() else widget.rect()


def _clear(box) -> None:
    """Empty *box*. Hidden at once: a widget only taken out of the layout keeps
    painting where it was until deleteLater runs."""
    while box.count():
        widget = box.takeAt(0).widget()
        widget.hide()
        widget.deleteLater()


_RING_PAD = 6
_CARD_WIDTH = 340
_MARGIN = 16


class TourOverlay(QWidget):
    """Dims the window, rings one control, and explains it."""

    finished = pyqtSignal()

    def __init__(self, host: QWidget, stops: Sequence[TourStop] = TOUR_STOPS,
                 *, tip: bool = False) -> None:
        super().__init__(host)
        self._host = host
        self._stops = list(stops)
        self._tip = tip
        self._index = 0
        self._hole: QRect | None = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._card = QFrame(self)
        self._card.setObjectName("tourCallout")
        _theme.style(self._card, "TOUR_CALLOUT")
        self._card.setFixedWidth(_CARD_WIDTH)
        card = QVBoxLayout(self._card)
        card.setContentsMargins(14, 12, 14, 12)
        card.setSpacing(6)
        self._step = QLabel()
        _theme.style(self._step, "TEXT_SM_MUTED")
        self._title = QLabel()
        _theme.style(self._title, "PANEL_HEADLINE")
        self._body = QLabel()
        self._body.setWordWrap(True)
        _theme.style(self._body, "PANEL_BODY")
        self._legend = QWidget()
        QVBoxLayout(self._legend).setContentsMargins(0, 4, 0, 0)
        self._themes = QWidget()
        QVBoxLayout(self._themes).setContentsMargins(0, 0, 0, 0)
        for w in (self._step, self._title, self._body, self._legend, self._themes):
            card.addWidget(w)
        row = QHBoxLayout()
        row.setContentsMargins(0, 6, 0, 0)
        self._end_btn = QPushButton("End tour")
        self._back_btn = QPushButton("Back")
        self._next_btn = QPushButton("Next")
        for btn, role in ((self._end_btn, "TOUR_BTN_GHOST"), (self._back_btn, "TOUR_BTN_GHOST"),
                          (self._next_btn, "SAVE_BTN")):
            _theme.style(btn, role)
        self._end_btn.setToolTip(f"Stop here. The tour stays in {TOUR_MENU_PATH}.")
        self._end_btn.clicked.connect(self.end)
        self._back_btn.clicked.connect(self.back)
        self._next_btn.clicked.connect(self.next)
        row.addWidget(self._end_btn)
        row.addStretch()
        row.addWidget(self._back_btn)
        row.addWidget(self._next_btn)
        card.addLayout(row)
        if tip:     # one card: no count, no way back, nothing to end early
            for w in (self._step, self._back_btn, self._end_btn):
                w.hide()
        host.installEventFilter(self)

    # ── driving it ──────────────────────────────────────────────────────────

    def start(self) -> None:
        self.setGeometry(self._host.rect())
        self.show()
        self.raise_()
        self.setFocus()
        self._go(0)

    def next(self) -> None:
        if self._index + 1 >= len(self._stops):
            self.end()
        else:
            self._go(self._index + 1)

    def back(self) -> None:
        if self._index > 0:
            self._go(self._index - 1)

    def end(self) -> None:
        self._host.removeEventFilter(self)
        self.hide()
        self.deleteLater()
        self.finished.emit()

    def current(self) -> int:
        return self._index

    def hole(self) -> QRect | None:
        """The ringed area, in this overlay's coordinates (None: card centred)."""
        return self._hole

    # ── layout and paint ────────────────────────────────────────────────────

    def _go(self, index: int) -> None:
        self._index = index
        stop = self._stops[index]
        last = index == len(self._stops) - 1
        self._step.setText(f"{index + 1} of {len(self._stops)}")
        self._title.setText(stop.title)
        self._body.setText(stop.body)
        self._fill_legend(stop.legend)
        self._fill_themes(stop.themes)
        self._back_btn.setEnabled(index > 0)
        self._next_btn.setText("Got it" if self._tip else ("Done" if last else "Next"))
        self._hole = self._target_rect(stop)
        self._place_card()
        self.update()

    def _fill_themes(self, show: bool) -> None:
        from streamselect.gui.tour_theme_picker import ThemeList

        box = self._themes.layout()
        _clear(box)
        if show:
            current = getattr(self._host.config, "theme_name", _theme.current_theme())
            picker = ThemeList(current)
            picker.picked.connect(self._pick_theme)
            box.addWidget(picker)
            picker.show()       # now, not queued: the card measures itself next
        self._themes.setVisible(show)

    def _pick_theme(self, name: str) -> None:
        # The Style menu's own handler: applies live and saves (no Apply step).
        self._host._set_theme_from_menu(name)
        self.update()

    def _fill_legend(self, legend: tuple[tuple[str, str], ...]) -> None:
        from streamselect.gui import icon_utils as _icon_utils

        box = self._legend.layout()
        _clear(box)
        for role, text in legend:
            row = QWidget()
            line = QHBoxLayout(row)
            line.setContentsMargins(0, 0, 0, 0)
            line.setSpacing(8)
            mark = QLabel()
            mark.setObjectName(f"tourLegend_{role}")
            # The row's own colours: live is the accent, the rest neutral
            # (channel_list_delegate._paint_kind_icon).
            color = _theme.COLOR_ACCENT if role == "live" else _theme.COLOR_TEXT
            mark.setPixmap(_icon_utils.role_pixmap(role, color, 18))
            mark.setAlignment(Qt.AlignmentFlag.AlignTop)
            label = QLabel(text)
            label.setWordWrap(True)
            _theme.style(label, "PANEL_BODY")
            line.addWidget(mark)
            line.addWidget(label, 1)
            box.addWidget(row)
            row.show()          # now, not queued: the card measures itself next
        self._legend.setVisible(bool(legend))

    def _target_rect(self, stop: TourStop) -> QRect | None:
        widget = stop.target(self._host)
        if widget is None or not widget.isVisible():
            return None
        if stop.area is not None:
            area = stop.area(widget)
            if area.isEmpty():
                return None
        else:
            area = _drawn_rect(widget) if stop.tight else widget.rect()
        top_left = widget.mapTo(self._host, area.topLeft())
        rect = QRect(top_left, area.size()).adjusted(-_RING_PAD, -_RING_PAD, _RING_PAD, _RING_PAD)
        return rect.intersected(self.rect())

    def _place_card(self) -> None:
        # The height for the card's FIXED width: the body wraps, and sizeHint
        # alone measured it on one line and cut the rest off.
        size = QSize(_CARD_WIDTH, self._card.layout().totalHeightForWidth(_CARD_WIDTH))
        area = self.rect().adjusted(_MARGIN, _MARGIN, -_MARGIN, -_MARGIN)
        hole = self._hole
        if hole is None or self._stops[self._index].centred:
            x = area.center().x() - size.width() // 2
            y = area.center().y() - size.height() // 2
        elif hole.bottom() + 12 + size.height() <= area.bottom():     # below
            x, y = hole.left(), hole.bottom() + 12
        elif hole.top() - 12 - size.height() >= area.top():            # above
            x, y = hole.left(), hole.top() - 12 - size.height()
        else:                                                          # beside
            x, y = hole.right() + 12, hole.top()
            if x + size.width() > area.right():
                x = hole.left() - 12 - size.width()
        x = max(area.left(), min(x, area.right() - size.width()))
        y = max(area.top(), min(y, area.bottom() - size.height()))
        self._card.setGeometry(x, y, size.width(), size.height())

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt API)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        scrim = QPainterPath()
        scrim.addRect(QRectF(self.rect()))
        if self._hole is not None:
            ring = QPainterPath()
            ring.addRoundedRect(QRectF(self._hole), 8, 8)
            scrim = scrim.subtracted(ring)
        painter.fillPath(scrim, to_qcolor(_theme.OVERLAY_BLACK_55))
        if self._hole is not None:
            painter.setPen(QPen(to_qcolor(_theme.COLOR_ACCENT), 2))
            painter.drawRoundedRect(QRectF(self._hole), 8, 8)

    # ── input ───────────────────────────────────────────────────────────────

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt API)
        if obj is self._host and event.type() == QEvent.Type.Resize:
            self.setGeometry(self._host.rect())
            self._go(self._index)
        return False

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt API)
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.end()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.next()
        elif key == Qt.Key.Key_Left:
            self.back()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt API)
        event.accept()      # the window underneath is paused while the tour runs


def start_tour(host) -> TourOverlay:
    """Start the tour over *host* (a MainWindow); one at a time."""
    from streamselect.gui.just_in_time_tips import TOUR_KEY, mark_seen

    running = host.__dict__.get("_tour")
    if running is not None:
        running.end()
    mark_seen(host, TOUR_KEY)       # taken once: never offered again
    tour = TourOverlay(host)
    host._tour = tour
    tour.finished.connect(lambda: _on_tour_finished(host, tour))
    tour.start()
    return tour


def _on_tour_finished(host, tour: TourOverlay) -> None:
    """Say where the tour lives, so it can be found again (user report, R8)."""
    if host.__dict__.get("_tour") is tour:
        host.__dict__.pop("_tour", None)
    host.notification_manager.show(
        title="Tour finished",
        message=f"Take it again any time from {TOUR_MENU_PATH}.",
        type="info", auto_dismiss_seconds=12)
