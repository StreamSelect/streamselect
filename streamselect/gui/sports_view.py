"""The Sports view: what is playing now, then what is on later, from stored games.

Layout is the settled Sports Desk direction (Variant C), narrowed to games:
every game on now is a card; later games are one-line rows under day
headings; finished games sit dimmed at the foot. Selecting a game lists every
channel that carries it ("Watch on"), each playable, with a guide-only listing
marked EPG. Double-clicking a game, or its play button, plays its best feed.

Reads only what the game finder stored (``core/games``) through the host's
``_run_query`` seam; it never parses a channel name. Only confirmed games
(Level 1: two or more independent collections agree) are shown for now.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from streamselect.core.epg_utils import (
    browse_day_separator_label, fmt_duration, fmt_time, now_utc, to_local,
)
from streamselect.core.games.read import (
    ENDING, ON_NOW, OVER, UPCOMING, GameDTO, best_feed, game_state, load_games,
)
from streamselect.core.games.store import enabled_leagues
from streamselect.core.repositories.provider import ProviderRepository
from streamselect.gui import cursor_affordance
from streamselect.gui import icon_utils as _icon_utils
from streamselect.gui import theme as _theme
from streamselect.gui.content_view import ContentView
from streamselect.gui.flow_layout import FlowLayout
from streamselect.gui.sidebar.base import GroupHeading

#: The sport this view shows. Hockey first (the method doc); others join once a
#: league of theirs passes the method's test and is listed in game_finder_leagues.
SPORT = "hockey"
#: Re-render this often while open: "1h 12m in" and on-now/finished move with the clock.
TICK_MS = 60_000
CARD_WIDTH = 300


def _game_key(g: GameDTO) -> tuple:
    return (g.league, g.team_a, g.team_b, g.start_utc)


class GameCard(QFrame):
    """One game on now: LIVE and how long in, the teams, league and channel count."""

    selected = pyqtSignal(object)      # GameDTO
    play = pyqtSignal(object)          # GameDTO

    def __init__(self, game: GameDTO, state: str, now: datetime, parent=None):
        super().__init__(parent)
        self.game = game
        self.setObjectName("gameCard")
        self.setFixedWidth(CARD_WIDTH)
        _theme.style(self, "GAME_CARD")
        cursor_affordance.set_clickable(self, True)
        self.setToolTip("Select to list every channel showing this game; double-click to play")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        elapsed = fmt_duration(game.start_utc, now)
        self.tag = QLabel(f"● LIVE · {elapsed} in" if state == ON_NOW
                          else f"LIKELY ENDING · {elapsed} in")
        _theme.style(self.tag, "GAME_LIVE_TAG" if state == ON_NOW else "TEXT_SM_MUTED")
        top.addWidget(self.tag)
        top.addStretch(1)
        self.play_button = _icon_utils.icon_button("episode", "Play this game's best channel")
        self.play_button.clicked.connect(lambda: self.play.emit(self.game))
        top.addWidget(self.play_button)
        lay.addLayout(top)

        self.title = QLabel(game.title)
        self.title.setWordWrap(True)
        _theme.style(self.title, "GAME_TITLE")
        lay.addWidget(self.title)
        n = len(game.playable)
        self.meta = QLabel(f"{game.league} · {n} channel{'' if n == 1 else 's'}"
                           f" · started {fmt_time(game.start_utc)}")
        _theme.style(self.meta, "TEXT_SM_MUTED")
        lay.addWidget(self.meta)

    def set_selected(self, on: bool) -> None:
        self.setProperty("selected", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt API)
        self.selected.emit(self.game)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt API)
        self.play.emit(self.game)
        super().mouseDoubleClickEvent(event)


class SportsView(ContentView):
    """Games on now as cards, later games as rows, finished games dimmed."""

    playRequested = pyqtSignal(str)      # channel id
    channelSelected = pyqtSignal(str)    # channel id: the details pane follows the selection

    def __init__(self, db, config, run_query: Callable, parent=None, *,
                 clock: Callable[[], datetime] = now_utc):
        super().__init__(config, parent)
        self._clock = clock
        self._db = db
        self._run_query = run_query
        self._token: list[int] = [0]
        self._games: list[GameDTO] = []
        self._selected: Optional[tuple] = None
        self._loaded = False
        self.settings = next((s for s in enabled_leagues() if s.sport == SPORT), None)

        self._tick = QTimer(self)
        self._tick.setInterval(TICK_MS)
        self._tick.timeout.connect(self._render)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)
        self._body = QWidget()
        scroll.setWidget(self._body)
        self._layout = QVBoxLayout(self._body)
        self._layout.setContentsMargins(16, 12, 16, 16)
        self._layout.setSpacing(8)
        self.cards: list[GameCard] = []
        self.feed_buttons: list[QPushButton] = []

    # ── lifecycle ──────────────────────────────────────────────────────────

    def on_activate(self) -> None:
        self.reload()
        self._tick.start()

    def on_deactivate(self) -> None:
        self._tick.stop()

    def reload(self) -> None:
        """Re-read the stored games off the UI thread, then render."""
        def query(repos):
            hidden = set(ProviderRepository(repos.session).get_hidden_provider_ids())
            return load_games(repos.session, SPORT, hidden, min_level=1, max_level=1)
        self._run_query(query, self._on_games, token_ref=self._token, on_error=self._on_error)

    def _on_games(self, games: list[GameDTO]) -> None:
        self._games = list(games or [])
        self._loaded = True
        self._render()

    def _on_error(self, _exc: Exception) -> None:
        self._games, self._loaded = [], True
        self._render(error=True)

    # ── rendering ──────────────────────────────────────────────────────────

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout() is not None:
                QWidget().setLayout(item.layout())
        self.cards, self.feed_buttons = [], []

    def _render(self, error: bool = False) -> None:
        self._clear()
        if not self._loaded:
            return
        if error:
            self._message("Games could not be loaded", "The game list will try again at the next refresh.")
            return
        if self.settings is None:
            self._message("No sport is set up yet", "")
            return
        now = self._clock()
        on_now, later, finished = [], [], []
        for g in self._games:
            state = game_state(g, now, self.settings)
            (on_now if state in (ON_NOW, ENDING) else later if state == UPCOMING else finished).append((g, state))
        on_now.sort(key=lambda gs: gs[0].start_utc, reverse=True)   # most recently started first

        self._layout.addWidget(GroupHeading("On now", len(on_now)))
        if on_now:
            grid_host = QWidget()
            grid = FlowLayout(grid_host, spacing=10)
            for g, state in on_now:
                card = GameCard(g, state, now)
                card.selected.connect(self._select)
                card.play.connect(self._play_best)
                card.set_selected(_game_key(g) == self._selected)
                grid.addWidget(card)
                self.cards.append(card)
            self._layout.addWidget(grid_host)
        else:
            nxt = later[0][0] if later else None
            self._message(f"No {SPORT} games on right now",
                          f"Next: {nxt.title}, {browse_day_separator_label(nxt.start_utc, now).split(' · ')[0]}"
                          f" at {fmt_time(nxt.start_utc)}." if nxt else "No games are listed yet.")

        chosen = next((g for g in self._games if _game_key(g) == self._selected), None)
        if chosen is not None and game_state(chosen, now, self.settings) != OVER:
            self._feeds_panel(chosen)

        day = None
        for g, _state in later:
            label = browse_day_separator_label(g.start_utc, now)
            if to_local(g.start_utc).date() != day:
                day = to_local(g.start_utc).date()
                self._layout.addWidget(GroupHeading(label, sum(
                    1 for x, _ in later if to_local(x.start_utc).date() == day)))
            self._layout.addWidget(self._row(g, fmt_time(g.start_utc)))

        if finished:
            self._layout.addWidget(GroupHeading("Finished", len(finished)))
            for g, _state in sorted(finished, key=lambda gs: gs[0].start_utc, reverse=True):
                row = self._row(g, fmt_time(g.start_utc))
                row.setEnabled(False)
                row.setToolTip("This game has ended")
                self._layout.addWidget(row)
        self._layout.addStretch(1)

    def _message(self, headline: str, body: str) -> None:
        h = QLabel(headline)
        _theme.style(h, "PANEL_HEADLINE")
        self._layout.addWidget(h)
        if body:
            b = QLabel(body)
            b.setWordWrap(True)
            _theme.style(b, "PANEL_BODY")
            self._layout.addWidget(b)

    def _row(self, g: GameDTO, when: str) -> QPushButton:
        n = len(g.playable)
        row = QPushButton(f"{when}    {g.title}    ·  {g.league} · {n} channel{'' if n == 1 else 's'}")
        _theme.style(row, "GAME_FEED_ROW")
        row.setToolTip("List every channel showing this game")
        row.clicked.connect(lambda _=False, game=g: self._select(game))
        return row

    def _feeds_panel(self, g: GameDTO) -> None:
        self._layout.addWidget(GroupHeading(f"Watch on · {g.title}", len(g.playable)))
        for f in g.playable:
            line = QWidget()
            h = QHBoxLayout(line)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)
            btn = QPushButton(f"{f.name}    —  {f.collection}")
            _theme.style(btn, "GAME_FEED_ROW")
            btn.setToolTip("Play this channel")
            btn.setProperty("channel_id", f.channel_id)
            btn.clicked.connect(lambda _=False, cid=f.channel_id: self.playRequested.emit(cid))
            h.addWidget(btn, 1)
            if f.from_guide:
                chip = QLabel("EPG")
                chip.setToolTip("Found in the programme guide, which is less reliable than channel names")
                _theme.style(chip, "GAME_GUIDE_CHIP")
                h.addWidget(chip)
            self.feed_buttons.append(btn)
            self._layout.addWidget(line)

    # ── actions ────────────────────────────────────────────────────────────

    def _select(self, game: GameDTO) -> None:
        key = _game_key(game)
        if key == self._selected:
            return
        self._selected = key
        feed = best_feed(game)
        if feed is not None:
            self.channelSelected.emit(feed.channel_id)
        QTimer.singleShot(0, self._render)    # not inside the clicked card's own event

    def _play_best(self, game: GameDTO) -> None:
        feed = best_feed(game)
        if feed is not None:
            self.playRequested.emit(feed.channel_id)
