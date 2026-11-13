"""The Sports view: the games on now, then later, then finished — from stored games.

Design: The Sports Desk rev 3 (SV-Q17-Q36, all answered 2026-11-12). Every
game on now is a card (``game_card.GameCard``); later and finished games are
rows under day / Finished headings, and any game opens the same channel list.
Section headers sit on the sidebar's header band and fold (Finished starts
folded); the sort order, the "Less certain games" toggle and the folds are
remembered (``Config.sports_view_state``). The user's preferred channel and
hidden channels are kept per league (``Config.game_channel_prefs``).

Reads only what the game finder stored (``core/games``) through the host's
``_run_query`` seam; it never parses a channel name.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from streamselect.core.epg_utils import browse_day_separator_label, fmt_time, now_utc, to_local
from streamselect.core.games.read import (
    event_is_live as event_live,
    ENDING, ON_NOW, UPCOMING, WRONG_CONTENT, GameDTO, arrange_feeds, best_feed, game_key, game_state,
    load_games, load_watch_history, mark_finished,
)
from streamselect.core.games.alerts import add_alert, alerts_for, load_alerts, remove_alerts, rule_for
from streamselect.core.games.store import enabled_leagues, sport_settings
from streamselect.core.repositories.provider import ProviderRepository
from streamselect.gui import cursor_affordance
from streamselect.gui import deferred_config_save as _cfgsave
from streamselect.gui import icon_utils as _icon_utils
from streamselect.gui import theme as _theme
from streamselect.gui.chips import ToggleChip
from streamselect.gui.content_view import ContentView
from streamselect.gui.flow_layout import FlowLayout
from streamselect.gui.game_card import (
    HIDE_CHANNEL, HIDE_COLLECTION, HIDE_EVERYWHERE, AlertBell, ChannelList, GameCard,
)
from streamselect.gui.sidebar.base import GroupHeading, _ClickableHeader
from streamselect.gui.similar_lightbox_card import _ClickableFrame

#: Sports are not named here: every sport with a league in ``game_finder_leagues``
#: gets its own section (owner, 2026-11-13: hockey is one segment, not the view).
#: Re-render this often while open: progress bars and on-now/finished move with the clock.
TICK_MS = 60_000
SORT_EARLIEST, SORT_LATEST = "earliest", "latest"
FINISHED = "finished"


def _game_key(g: GameDTO) -> tuple:
    return (g.league, g.team_a, g.team_b, g.start_utc)


class SportsView(ContentView):
    """Games on now as cards, later and finished games as rows; see the module docstring."""

    playRequested = pyqtSignal(str)           # channel id
    channelSelected = pyqtSignal(str)         # channel id: the details pane follows an opened game
    hideEverywhereRequested = pyqtSignal(str)  # channel id: the app's own Hide
    alertsChanged = pyqtSignal()              # a bell added or removed a rule: Watch Alerts re-reads

    def __init__(self, db, config, run_query: Callable, parent=None, *,
                 clock: Callable[[], datetime] = now_utc):
        super().__init__(config, parent)
        self._clock = clock
        self._db = db
        self._run_query = run_query
        self._token: list[int] = [0]
        self._raw: list[GameDTO] = []
        self._history: dict = {}
        self._alerts: list = []
        self._open: Optional[tuple] = None
        self._show_hidden: set[tuple] = set()
        self._playing: Optional[str] = None
        self._loaded = False
        self._finding = False
        #: sport -> its settings (the first listed league's lengths), in listed order.
        self.sports: dict = sport_settings()

        self._tick = QTimer(self)
        self._tick.setInterval(TICK_MS)
        self._tick.timeout.connect(self._render)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        # The centre panel never scrolls sideways: cards wrap, long names elide.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)
        self._body = QWidget()
        scroll.setWidget(self._body)
        self._layout = QVBoxLayout(self._body)
        self._layout.setContentsMargins(16, 12, 16, 16)
        self._layout.setSpacing(8)
        self.cards: list[GameCard] = []
        self.rows: list[QPushButton] = []
        self.headers: dict[str, QWidget] = {}
        self._render()          # "Loading games…" until the first read comes back

    # ── remembered state ───────────────────────────────────────────────────

    def _state(self) -> dict:
        return self.config.sports_view_state

    def _save(self) -> None:
        _cfgsave.save_soon(self)

    def _prefs(self, league_key: str) -> dict:
        return self.config.game_channel_prefs.setdefault(league_key, {})

    @property
    def sort_order(self) -> str:
        return self._state().get("sort", SORT_EARLIEST)

    @property
    def less_certain(self) -> bool:
        return bool(self._state().get("less_certain", False))

    def _folded(self) -> set[str]:
        """Folded section keys, each ``"<sport>:<section>"`` or ``"sport:<sport>"``."""
        st = self._state()
        if "folded" not in st:
            st["folded"] = [f"{sp}:{FINISHED}" for sp in self.sports]   # Finished starts folded (SV-Q21)
        elif FINISHED in st["folded"]:            # remembered before sports had sections: it was hockey's
            st["folded"] = [f"hockey:{FINISHED}" if k == FINISHED else k for k in st["folded"]]
        return set(st["folded"])

    # ── lifecycle ──────────────────────────────────────────────────────────

    def on_activate(self) -> None:
        self.reload()
        self._tick.start()

    def on_deactivate(self) -> None:
        self._tick.stop()

    def reload(self) -> None:
        """Re-read the stored games and the play log off the UI thread, then render."""
        top = 2 if self.less_certain else 1

        def query(repos):
            hidden = set(ProviderRepository(repos.session).get_hidden_provider_ids())
            games = [g for sp in self.sports for g in load_games(repos.session, sp, hidden, 1, top)]
            return games, load_watch_history(repos.session), load_alerts(repos.session)
        self._run_query(query, self._on_games, token_ref=self._token, on_error=self._on_error)

    def set_finding(self, on: bool) -> None:
        """The game finder has started looking (True) — say so instead of a premature count.

        ``False`` only records it; the next render shows the new state, so a view
        that is re-reading never flashes the OLD (empty) list in between.
        """
        if on != self._finding:
            self._finding = on
            if on:
                self._render()

    def finished_finding(self) -> None:
        """The finder stored its games: re-read, and drop "finding" when they arrive."""
        self._finding = False
        if self.isVisible():
            self.reload()

    def set_playing(self, channel_id: Optional[str]) -> None:
        """The channel now playing (the host's player poll), or None."""
        if channel_id != self._playing:
            self._playing = channel_id
            if self._loaded:
                # Re-read, not just re-draw: the play log just changed, and the order
                # of each game's channels follows what was last watched.
                self.reload()

    def _on_games(self, result) -> None:
        games, history, alerts = result if result else ([], {}, [])
        self._raw, self._history, self._alerts = list(games or []), dict(history or {}), list(alerts or [])
        self._loaded = True
        self._render()

    def _on_error(self, _exc: Exception) -> None:
        self._raw, self._loaded = [], True
        self._render(error=True)

    # ── rendering ──────────────────────────────────────────────────────────

    def _games(self) -> list[GameDTO]:
        out = []
        for g in self._raw:
            g = arrange_feeds(g, self._prefs(g.league_key), self._history, self._clock())
            if g.playable:
                out.append(g)
        return out

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()            # now: deleteLater waits for the event loop
                w.deleteLater()
            elif item.layout() is not None:
                QWidget().setLayout(item.layout())
        self.cards, self.rows, self.headers = [], [], {}

    def _render(self, error: bool = False) -> None:
        self._clear()
        if not self._loaded:
            self._message("Loading games…", "")
            return
        games = self._games() if not error else []
        if self._finding and not games:
            # Never "0 games" before the finder has looked: on a fresh launch the
            # table is empty until the first run stores what it found.
            self._message("Finding games in your channel listings…",
                          "This takes a few seconds after the app starts or a source refreshes.")
            return
        if error:
            self._message("Games could not be loaded", "The game list will try again at the next refresh.")
            return
        if not self.sports:
            self._message("No sport is set up yet", "")
            return
        now = self._clock()
        self._layout.addWidget(self._toolbar())
        if self._finding:
            looking = QLabel("Looking for new games…")
            _theme.style(looking, "TEXT_SM_MUTED")
            self._layout.addWidget(looking)
        folded = self._folded()
        for sport, settings in self.sports.items():
            mine = [g for g in games if g.sport == sport]
            live = sum(1 for g in mine if event_live(g, now, settings))
            self._layout.addWidget(self._sport_header(sport, mine, live))
            if f"sport:{sport}" not in folded:
                self._render_sport(sport, settings, mine, now, folded)
        self._layout.addStretch(1)

    def _render_sport(self, sport: str, settings, games: list, now: datetime, folded: set) -> None:
        """One sport's segment: On now, the days to come, Finished (keys prefixed by sport)."""
        on_now, later, finished = [], [], []
        for g in games:
            state = game_state(g, now, settings)
            (on_now if state in (ON_NOW, ENDING) else later if state == UPCOMING else finished).append((g, state))
        on_now.sort(key=lambda gs: gs[0].start_utc, reverse=self.sort_order == SORT_LATEST)

        on_key = f"{sport}:on_now"
        self._layout.addWidget(self._header(on_key, "On now", len(on_now), foldable=True))
        if on_key in self._folded():
            pass                             # folded like any other section (owner, 2026-11-13)
        elif on_now:
            opened = [gs for gs in on_now if _game_key(gs[0]) == self._open]
            for g, state in opened:          # the open game spans the full width, first (SV-Q17)
                self._layout.addWidget(self._card(g, state, now, expanded=True))
            rest = [gs for gs in on_now if gs not in opened]
            if rest:
                grid_host = QWidget()
                grid = FlowLayout(grid_host, spacing=10)
                for g, state in rest:
                    grid.addWidget(self._card(g, state, now))
                self._layout.addWidget(grid_host)
        else:
            nxt = later[0][0] if later else None
            self._message(f"No {sport} games on right now",
                          f"Next: {nxt.title}, {browse_day_separator_label(nxt.start_utc, now).split(' · ')[0]}"
                          f" at {fmt_time(nxt.start_utc)}." if nxt else "No games are listed yet.")

        days: dict = {}
        for g, _ in later:
            days.setdefault(to_local(g.start_utc).date(), []).append(g)
        for day, gs in days.items():
            key = f"{sport}:day:{day.isoformat()}"
            self._layout.addWidget(self._header(key, browse_day_separator_label(gs[0].start_utc, now),
                                                len(gs), foldable=True))
            if key not in folded:
                for g in gs:
                    self._game_row(g, playable=False)

        if finished:
            key = f"{sport}:{FINISHED}"
            self._layout.addWidget(self._header(key, "Finished", len(finished), foldable=True))
            if key not in folded:
                for g, _ in sorted(finished, key=lambda gs: gs[0].start_utc, reverse=True):
                    self._game_row(g, playable=True)

    def _message(self, headline: str, body: str) -> None:
        h = QLabel(headline)
        _theme.style(h, "PANEL_HEADLINE")
        self._layout.addWidget(h)
        if body:
            b = QLabel(body)
            b.setWordWrap(True)
            _theme.style(b, "PANEL_BODY")
            self._layout.addWidget(b)

    def _header(self, key: str, label: str, count: int, *, foldable: bool,
                controls: Optional[QWidget] = None) -> QWidget:
        """A section header on the sidebar's header band (SECTION_HEADER_TINT).

        A foldable one folds on a click ANYWHERE on the band — caret, label or empty
        space (owner report: only the label worked, and the caret did nothing). It is
        the sidebar's own ``_ClickableHeader``; the heading inside stays passive so
        one click is one toggle.
        """
        tip = ("Show these games" if key in self._folded() else "Fold these games") if foldable else ""
        if foldable:
            band = _ClickableHeader()
            band.setToolTip(tip)
            band.clicked.connect(lambda k=key: self._toggle_fold(k))
        else:
            band = QWidget()
            band.setObjectName("sectionHeader")
            band.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            _theme.style(band, "SECTION_HEADER_TINT")
        h = QHBoxLayout(band)
        h.setContentsMargins(6, 3, 6, 3)
        h.setSpacing(6)
        if foldable:
            caret = QLabel()
            _icon_utils.set_label_icon(caret, "expand" if key in self._folded() else "collapse", 12)
            h.addWidget(caret)
        heading = GroupHeading(label, count, tooltip=tip)
        h.addWidget(heading, 1)
        if controls is not None:
            h.addWidget(controls)
        self.headers[key] = band
        return band

    def _sport_header(self, sport: str, games: list, live: int) -> QWidget:
        """The sport's own header: its name, its leagues, how many are live; folds the segment."""
        key = f"sport:{sport}"
        # The whole band folds, not just the name (owner report: only the word worked).
        band = _ClickableFrame()
        cursor_affordance.set_clickable(band)
        band.setToolTip(f"Show {sport}" if key in self._folded() else f"Fold {sport}")
        band.clicked.connect(lambda k=key: self._toggle_fold(k))
        h = QHBoxLayout(band)
        h.setContentsMargins(2, 10, 6, 2)
        h.setSpacing(8)
        caret = QLabel()
        _icon_utils.set_label_icon(caret, "expand" if key in self._folded() else "collapse", 14)
        h.addWidget(caret)
        glyph = QLabel()                          # the sport's own glyph (icons.VECTOR_KEYS sport_*)
        _theme.style(glyph, "PANEL_HEADLINE")
        _icon_utils.set_label_icon(glyph, f"sport_{sport}", 18)
        h.addWidget(glyph)
        name = QLabel(sport.title())
        _theme.style(name, "PANEL_HEADLINE")
        h.addWidget(name)
        leagues = sorted({g.league for g in games} or {s.league for s in enabled_leagues() if s.sport == sport})
        meta = QLabel(" · ".join(leagues) + (f" · {live} live" if live else ""))
        _theme.style(meta, "TEXT_SM_MUTED")
        h.addWidget(meta)
        h.addStretch(1)
        self.headers[key] = band
        return band

    def _toolbar(self) -> QWidget:
        """View-wide controls (they apply to every sport): sort order, less certain games."""
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        h.addStretch(1)
        self.sort_button = QPushButton("Earliest first" if self.sort_order == SORT_EARLIEST else "Latest first")
        self.sort_button.setFlat(True)
        _icon_utils.set_button_icon(self.sort_button, "sort")
        _theme.style(self.sort_button, "LINK_BTN_SM")
        self.sort_button.setToolTip("Order the games on now by when they started — click to reverse")
        self.sort_button.clicked.connect(self._toggle_sort)
        h.addWidget(self.sort_button)
        self.less_certain_chip = ToggleChip("Less certain games", enabled=self.less_certain)
        self.less_certain_chip.setToolTip("Also show games only one collection lists (dashed outline)")
        self.less_certain_chip.toggled_changed.connect(self._toggle_less_certain)
        h.addWidget(self.less_certain_chip)
        return box

    def _card(self, g: GameDTO, state: str, now: datetime, *, expanded: bool = False) -> GameCard:
        channels = self._channel_list(g) if expanded else None
        card = GameCard(g, state, now, self.sports[g.sport].usual_length, expanded=expanded,
                        playing_id=self._playing, channels=channels,
                        alerts=alerts_for(g, self._alerts))
        card.bell.toggled_rule.connect(self._set_alert)
        card.play.connect(self.playRequested)
        card.toggled.connect(self._toggle_open)
        card.finished.connect(self._mark_finished)
        self.cards.append(card)
        return card

    def _channel_list(self, g: GameDTO) -> ChannelList:
        lst = ChannelList(g, preferred_key=self._prefs(g.league_key).get("preferred"),
                          playing_id=self._playing, show_hidden=_game_key(g) in self._show_hidden)
        lst.play.connect(self.playRequested)
        lst.prefer.connect(self._set_preferred)
        lst.hideRequested.connect(self._hide)
        lst.unhideRequested.connect(self._unhide)
        lst.reportRequested.connect(self._report)
        lst.clearReportsRequested.connect(self._clear_reports)
        if lst.hidden_button is not None:
            lst.hidden_button.clicked.connect(lambda _=False, k=_game_key(g): self._toggle_show_hidden(k))
        return lst

    def _game_row(self, g: GameDTO, *, playable: bool) -> None:
        """A later or finished game: one row; click opens its channel list beneath it (SV-Q23)."""
        when = fmt_time(g.start_utc)
        row = QPushButton(f"{when}    {g.title}    ·  {g.league}")
        _theme.style(row, "GAME_FEED_ROW")
        row.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        is_open = _game_key(g) == self._open
        row.setToolTip("Fold its channel list" if is_open else "List every channel that will show this game")
        row.clicked.connect(lambda _=False, game=g: self._toggle_open(game))
        line = QWidget()
        h = QHBoxLayout(line)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        h.addWidget(row, 1)
        bell = AlertBell(g, alerts_for(g, self._alerts))
        bell.toggled_rule.connect(self._set_alert)
        if bell.covering and not playable:
            on = QLabel("ALERT ON")            # words with the colour (B2)
            _theme.style(on, "GAME_LIVE_TAG")
            h.addWidget(on)
        h.addWidget(bell)
        row.bell = bell
        self._layout.addWidget(line)
        self.rows.append(row)
        if is_open:
            self._layout.addWidget(self._channel_list(g))

    # ── actions ────────────────────────────────────────────────────────────

    def _toggle_open(self, game: GameDTO) -> None:
        key = _game_key(game)
        self._open = None if key == self._open else key
        if self._open is not None:
            feed = best_feed(game)
            if feed is not None:
                self.channelSelected.emit(feed.channel_id)
        QTimer.singleShot(0, self._render)    # not inside the clicked widget's own event

    def _toggle_fold(self, key: str) -> None:
        folded = self._folded()
        folded.symmetric_difference_update({key})
        self._state()["folded"] = sorted(folded)
        self._save()
        QTimer.singleShot(0, self._render)

    def _toggle_sort(self) -> None:
        self._state()["sort"] = SORT_LATEST if self.sort_order == SORT_EARLIEST else SORT_EARLIEST
        self._save()
        QTimer.singleShot(0, self._render)

    def _toggle_less_certain(self, on: bool) -> None:
        self._state()["less_certain"] = bool(on)
        self._save()
        self.reload()

    def _toggle_show_hidden(self, key: tuple) -> None:
        self._show_hidden.symmetric_difference_update({key})
        QTimer.singleShot(0, self._render)

    def _set_preferred(self, game: GameDTO, feed) -> None:
        prefs = self._prefs(game.league_key)
        if feed is None:
            prefs.pop("preferred", None)
        else:
            prefs["preferred"] = feed.collection_key
        self._save()
        QTimer.singleShot(0, self._render)

    def _hide(self, game: GameDTO, feed, scope: str) -> None:
        if scope == HIDE_EVERYWHERE:
            self.hideEverywhereRequested.emit(feed.channel_id)
            return
        prefs = self._prefs(game.league_key)
        field, value = (("hidden_channels", feed.channel_id) if scope == HIDE_CHANNEL
                        else ("hidden_collections", feed.collection_key))
        if scope in (HIDE_CHANNEL, HIDE_COLLECTION) and value not in prefs.setdefault(field, []):
            prefs[field].append(value)
        if prefs.get("preferred") == feed.collection_key and scope == HIDE_COLLECTION:
            prefs.pop("preferred")
        self._save()
        QTimer.singleShot(0, self._render)

    def _unhide(self, game: GameDTO, feed) -> None:
        prefs = self._prefs(game.league_key)
        for field, value in (("hidden_channels", feed.channel_id), ("hidden_collections", feed.collection_key)):
            if value in prefs.get(field, []):
                prefs[field].remove(value)
        self._save()
        QTimer.singleShot(0, self._render)

    def _set_alert(self, game: GameDTO, kind: str, side: str, on: bool) -> None:
        """Add or remove one event-alert rule (SV-Q26), off the UI thread, then re-read."""
        rule = rule_for(kind, game, side)

        def write(repos):
            if on:
                add_alert(repos.session, rule)
            else:
                remove_alerts(repos.session, [a.id for a in load_alerts(repos.session)
                                              if (a.sides, a.mode, a.event) == (rule.sides, rule.mode, rule.event)])
        def done(_r) -> None:
            self.reload()
            self.alertsChanged.emit()
        self._run_query(write, done, commit=True)

    def _report(self, game: GameDTO, feed, kind: str) -> None:
        """Record a channel report against its collection, for this league (SV-Q37)."""
        entry = {"kind": kind, "at": self._clock().isoformat()}
        if kind == WRONG_CONTENT:
            entry["game"] = game_key(game)
        self._prefs(game.league_key).setdefault("reports", {}).setdefault(feed.collection_key, []).append(entry)
        self._save()
        QTimer.singleShot(0, self._render)

    def _clear_reports(self, game: GameDTO, feed) -> None:
        reports = self._prefs(game.league_key).get("reports") or {}
        if reports.pop(feed.collection_key, None) is not None:
            self._save()
        QTimer.singleShot(0, self._render)

    def _mark_finished(self, game: GameDTO) -> None:
        ended = self._clock()
        self._run_query(lambda repos: mark_finished(repos.session, game, ended),
                        lambda _r: self.reload(), commit=True)
