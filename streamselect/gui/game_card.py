"""A game on the Sports view: its card, and the list of channels showing it.

Design: The Sports Desk rev 3 (SV-Q17-Q36). Built from existing parts — the
shared progress bar, the details pane's chip, the region/quality chips, the
icon button factory — so nothing here draws its own copy of something the app
already draws.

* A card: LIVE or the start time · title · progress bar (times in its tooltip)
  · league · the play line "▶ [US] STATION" (one click plays) with a live-mark
  "+N" chip that opens the card. Double-click anywhere plays the same channel.
* An open card lists every channel: click a name to play it; a PREFERRED chip
  (solid on your pick, dashed on a hovered row) and an eye (hide, on hover)
  are the only controls. Hidden channels are counted, never silently gone.
* While a channel plays, the top line reads PLAYING in green and the row is
  marked where it is; the list never reorders under the cursor.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from streamselect.core.epg_utils import fmt_time
from streamselect.core.games.read import (
    DIDNT_PLAY, ENDING, ON_NOW, UPCOMING, WRONG_CONTENT, GameDTO, GameFeedDTO,
)
from streamselect.gui import cursor_affordance, icons
from streamselect.gui import icon_utils as _icon_utils
from streamselect.gui import theme as _theme
from streamselect.gui.badge_utils import make_quality_chip, make_region_chip
from streamselect.gui.detail_chips import make_chip
from streamselect.gui.progress_paint import ProgressBar, elapsed_pct

#: Width of a closed card (SV-Q22: fixed for now, revisit after use).
CARD_WIDTH = 280

#: Hide scopes the eye's menu offers (SV-Q28).
HIDE_CHANNEL, HIDE_COLLECTION, HIDE_EVERYWHERE = "channel", "collection", "everywhere"


def _keep_space(*widgets: QWidget) -> None:
    """A control that appears on hover keeps its space hidden, so rows never shift."""
    for w in widgets:
        sp = w.sizePolicy()
        sp.setRetainSizeWhenHidden(True)
        w.setSizePolicy(sp)


class ChannelRow(QWidget):
    """One channel showing a game: [country] station · EPG · quality · PREFERRED · eye."""

    play = pyqtSignal(str)                    # channel id
    prefer = pyqtSignal(object)               # GameFeedDTO, or None to clear
    hideRequested = pyqtSignal(object, str)   # GameFeedDTO, scope (never `hide`: that shadows QWidget.hide)
    unhideRequested = pyqtSignal(object)      # GameFeedDTO
    reportRequested = pyqtSignal(object, str)  # GameFeedDTO, kind (DIDNT_PLAY / WRONG_CONTENT)
    clearReportsRequested = pyqtSignal(object)  # GameFeedDTO

    def __init__(self, feed: GameFeedDTO, league: str, *, preferred: bool, playing: bool,
                 hidden: bool = False, parent=None):
        super().__init__(parent)
        self.feed = feed
        self._preferred = preferred
        self._hidden = hidden
        self._league = league
        self.setObjectName("gameChannelRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        _theme.style(self, "GAME_CHANNEL_ROW")
        if not hidden:
            cursor_affordance.set_clickable(self, True)
            self.setToolTip(f"Click to play\n{feed.name}\n{feed.channel_collection or feed.collection}")
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 1, 2, 1)
        row.setSpacing(4)
        if playing:
            mark = QLabel()
            _theme.style(mark, "GAME_PLAYING_NAME")
            _icon_utils.set_label_icon(mark, "play", 12)
            row.addWidget(mark)
        if feed.region:
            row.addWidget(make_region_chip(feed.region, self))
        self.report_icon = None
        if feed.report:
            # One small icon, no chip (owner, SV-Q39); the tooltip says what and how often.
            self.report_icon = QLabel()
            _theme.style(self.report_icon, "TEXT_SM_MUTED")
            _icon_utils.set_label_icon(self.report_icon, "reported", 12)
            self.report_icon.setToolTip(feed.report)
            row.addWidget(self.report_icon)
        self.name = QLabel(feed.station)
        self.name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        _theme.style(self.name, "GAME_PLAYING_NAME" if playing else
                     "TEXT_SM_MUTED" if hidden else "CHANNEL_NAME_LIVE")
        row.addWidget(self.name, 1)
        if feed.from_guide:
            epg = QLabel("EPG")
            epg.setToolTip("Found in the programme guide, which is less reliable than channel names")
            _theme.style(epg, "GAME_GUIDE_CHIP")
            row.addWidget(epg)
        if feed.quality:
            row.addWidget(make_quality_chip(feed.quality, self))
        if hidden:
            self.eye = _icon_utils.icon_button("visibility_toggle", f"Show this channel again in {league} games", px=13)
            self.eye.clicked.connect(lambda: self.unhideRequested.emit(self.feed))
            row.addWidget(self.eye)
            self.pref_chip = None
            return
        # PREFERRED: one chip, label and button (owner, SV-Q29 follow-up).
        self.pref_chip = make_chip("PREFERRED", "COLOR_TEXT_HI" if preferred else "COLOR_MUTED",
                                   dashed=not preferred, selected=preferred)
        self.pref_chip.setToolTip(f"Your preferred channel for {league} games — click to clear" if preferred
                                  else f"Make this your preferred channel for {league} games")
        self.pref_chip.clicked.connect(lambda: self.prefer.emit(None if self._preferred else self.feed))
        self.pref_chip.setVisible(preferred)
        row.addWidget(self.pref_chip)
        self.eye = _icon_utils.icon_button("hide", f"Hide this channel from {league} games", px=13)
        self.eye.clicked.connect(lambda: self._hide_menu(league))
        self.eye.setVisible(False)
        row.addWidget(self.eye)
        _keep_space(self.pref_chip, self.eye)

    def _add_hide_actions(self, menu: QMenu, league: str) -> None:
        for label, scope in ((f"Hide this channel from {league} games", HIDE_CHANNEL),
                             (f"Hide \u201c{self.feed.station}\u201d from {league} games", HIDE_COLLECTION)):
            menu.addAction(label).triggered.connect(lambda _=False, s=scope: self.hideRequested.emit(self.feed, s))
        menu.addSeparator()
        menu.addAction("Hide this channel everywhere\u2026").triggered.connect(
            lambda: self.hideRequested.emit(self.feed, HIDE_EVERYWHERE))

    def _hide_menu(self, league: str) -> None:
        menu = QMenu(self)
        self._add_hide_actions(menu, league)
        menu.exec(self.eye.mapToGlobal(QPoint(0, self.eye.height())))

    def build_context_menu(self, league: str) -> QMenu:
        """Every channel action in one place: play, preferred, hide, then a
        "Report this channel" section (owner, SV-Q39)."""
        menu = QMenu(self)
        menu.addAction("Play").triggered.connect(lambda: self.play.emit(self.feed.channel_id))
        menu.addAction(f"Clear PREFERRED for {league} games" if self._preferred
                       else f"Make PREFERRED for {league} games").triggered.connect(
            lambda: self.prefer.emit(None if self._preferred else self.feed))
        self._add_hide_actions(menu.addMenu(f"Hide from {league} games"), league)
        menu.addSection("Report this channel")
        menu.addAction("Didn't play").triggered.connect(
            lambda: self.reportRequested.emit(self.feed, DIDNT_PLAY))
        menu.addAction("Wrong content").triggered.connect(
            lambda: self.reportRequested.emit(self.feed, WRONG_CONTENT))
        clear = menu.addAction("Clear bad reports")
        clear.setEnabled(bool(self.feed.report))
        clear.triggered.connect(lambda: self.clearReportsRequested.emit(self.feed))
        return menu

    def contextMenuEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self._hidden:
            return
        self.build_context_menu(self._league).exec(event.globalPos())

    # Controls appear on hover only (or when active: your PREFERRED chip stays).
    def enterEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self.pref_chip is not None:
            self.pref_chip.setVisible(True)
            self.eye.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self.pref_chip is not None:
            self.pref_chip.setVisible(self._preferred)
            self.eye.setVisible(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if event.button() == Qt.MouseButton.LeftButton and not self._hidden and self.feed.channel_id:
            self.play.emit(self.feed.channel_id)
        super().mousePressEvent(event)


class ChannelList(QWidget):
    """Every channel showing a game, then "N hidden channels · show" when some are hidden."""

    play = pyqtSignal(str)
    prefer = pyqtSignal(object, object)       # GameDTO, GameFeedDTO | None
    hideRequested = pyqtSignal(object, object, str)   # GameDTO, GameFeedDTO, scope
    unhideRequested = pyqtSignal(object, object)      # GameDTO, GameFeedDTO
    reportRequested = pyqtSignal(object, object, str)  # GameDTO, GameFeedDTO, kind
    clearReportsRequested = pyqtSignal(object, object)  # GameDTO, GameFeedDTO

    def __init__(self, game: GameDTO, *, preferred_key: Optional[str], playing_id: Optional[str],
                 show_hidden: bool, parent=None):
        super().__init__(parent)
        self.game = game
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(1)
        self.rows: list[ChannelRow] = []
        for f in game.playable:
            r = ChannelRow(f, game.league, preferred=f.collection_key == preferred_key,
                           playing=f.channel_id == playing_id)
            r.play.connect(self.play)
            r.prefer.connect(lambda feed: self.prefer.emit(self.game, feed))
            r.hideRequested.connect(lambda feed, scope: self.hideRequested.emit(self.game, feed, scope))
            r.reportRequested.connect(lambda feed, kind: self.reportRequested.emit(self.game, feed, kind))
            r.clearReportsRequested.connect(lambda feed: self.clearReportsRequested.emit(self.game, feed))
            lay.addWidget(r)
            self.rows.append(r)
        hidden = [f for f in game.hidden if f.channel_id]
        self.hidden_button = None
        if hidden:
            n = len(hidden)
            self.hidden_button = QPushButton(f"{n} hidden channel{'' if n == 1 else 's'} · "
                                             f"{'hide' if show_hidden else 'show'}")
            self.hidden_button.setFlat(True)
            _theme.style(self.hidden_button, "LINK_BTN_SM")
            self.hidden_button.setToolTip("The channels you hid from these games, to bring one back"
                                          if not show_hidden else "Fold the hidden channels away")
            lay.addWidget(self.hidden_button, 0, Qt.AlignmentFlag.AlignLeft)
            if show_hidden:
                for f in hidden:
                    r = ChannelRow(f, game.league, preferred=False, playing=False, hidden=True)
                    r.unhideRequested.connect(lambda feed: self.unhideRequested.emit(self.game, feed))
                    lay.addWidget(r)


class AlertBell(QPushButton):
    """The event's alert bell (SV-Q24-Q26, look B2 — SV-Q25).

    Off: the EPG agenda's slashed bell. On (any rule covers the event): the
    ``alert`` bell in the accent. Click toggles an alert for THIS event;
    right-click offers this event / every event of either side / whenever these
    two meet, each a check item.

    ``over``: the event has finished. "This event" means nothing then, but a team or
    matchup alert does (owner, 2026-11-13), so the bell offers only those, and a
    click opens that menu.
    """

    toggled_rule = pyqtSignal(object, str, str, bool)   # GameDTO, kind, side, on

    def __init__(self, game: GameDTO, covering: list, parent=None, *, over: bool = False):
        super().__init__(parent)
        from streamselect.core.games.alerts import EITHER_SIDE, THESE_TWO, THIS_EVENT, rule_for
        self.game = game
        self._over = over
        # Over: a one-event rule still on file for it (until it expires) lights nothing.
        self.covering = [a for a in covering if not (over and a.event)]
        self.setFlat(True)
        self.setFixedWidth(26)
        on = bool(self.covering)
        if on:
            _icon_utils.set_button_icon(self, "alert", color=_theme.COLOR_ACCENT)
        else:
            _icon_utils.set_button_icon(self, "monitor_off")
        if over:
            self.setToolTip("Alerting for these teams' events — click to change" if on
                            else "Alert me for these teams' next events")
        else:
            self.setToolTip("Alert set — click to stop alerting for this event; right-click for more"
                            if on else "Alert me before this event starts (right-click for more)")
        self._kinds = [] if over else [(THIS_EVENT, "", "Alert me for this event")]
        self._kinds += [(EITHER_SIDE, game.team_a, f"Alert me for every {game.team_a} event"),
                       (EITHER_SIDE, game.team_b, f"Alert me for every {game.team_b} event"),
                       (THESE_TWO, "", f"Alert me whenever {game.team_a} meet {game.team_b}")]
        self._rule_for = rule_for
        self.clicked.connect(self._toggle_this)

    def _has(self, kind: str, side: str) -> bool:
        want = self._rule_for(kind, self.game, side)
        return any(a.sides == want.sides and a.mode == want.mode and a.event == want.event
                   for a in self.covering)

    def _toggle_this(self) -> None:
        from streamselect.core.games.alerts import THIS_EVENT
        if self._over or (self.covering and not self._has(THIS_EVENT, "")):
            self.build_menu().exec(self.mapToGlobal(QPoint(0, self.height())))
            return
        self.toggled_rule.emit(self.game, THIS_EVENT, "", not self._has(THIS_EVENT, ""))

    def build_menu(self) -> QMenu:
        menu = QMenu(self)
        for kind, side, label in self._kinds:
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(self._has(kind, side))
            act.triggered.connect(lambda on, k=kind, s=side: self.toggled_rule.emit(self.game, k, s, on))
        return menu

    def contextMenuEvent(self, event) -> None:  # noqa: N802 (Qt API)
        self.build_menu().exec(event.globalPos())


class PlayLine(QFrame):
    """The card's "▶ [US] STATION" line; ``clicked`` on a left press when playable."""

    clicked = pyqtSignal()

    def __init__(self, playable: bool, parent=None):
        super().__init__(parent)
        self._playable = playable
        self.setObjectName("gamePlayLine")
        _theme.style(self, "GAME_PLAY_LINE")
        if playable:
            cursor_affordance.set_clickable(self, True)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self._playable and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            return
        super().mousePressEvent(event)


class GameCard(QFrame):
    """A game on now (or about to start): see the module docstring."""

    play = pyqtSignal(str)                    # channel id
    toggled = pyqtSignal(object)              # GameDTO: open / close the channel list
    finished = pyqtSignal(object)             # GameDTO: the user marked it over

    def __init__(self, game: GameDTO, state: str, now: datetime, usual_length, *,
                 expanded: bool = False, playing_id: Optional[str] = None,
                 channels: Optional[ChannelList] = None, alerts: Optional[list] = None, parent=None):
        super().__init__(parent)
        self.game = game
        self.state = state
        self.setObjectName("gameCard")
        self.setProperty("selected", "true" if expanded else "false")
        self.setProperty("certain", "true" if game.level == 1 else "false")
        _theme.style(self, "GAME_CARD")
        if expanded:
            self.setMinimumWidth(CARD_WIDTH)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        else:
            self.setFixedWidth(CARD_WIDTH)
        if game.level != 1:
            self.setToolTip("Only one collection lists this game, so it is less certain")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(5)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        live = state in (ON_NOW, ENDING)
        self.tag = QLabel(f"{icons.status_dot_icon} LIVE" if state == ON_NOW
                          else "LIKELY ENDING" if state == ENDING else fmt_time(game.start_utc))
        _theme.style(self.tag, "GAME_LIVE_TAG" if state == ON_NOW else "TEXT_SM_MUTED")
        top.addWidget(self.tag)
        if live:
            started = QLabel(f"started {fmt_time(game.start_utc)}")
            _theme.style(started, "TEXT_SM_MUTED")
            top.addWidget(started)
        top.addStretch(1)
        self.bell = AlertBell(game, alerts or [])
        if self.bell.covering and state == UPCOMING:
            on = QLabel("ALERT ON")            # words with the colour, never colour alone (B2)
            _theme.style(on, "GAME_LIVE_TAG")
            top.addWidget(on)
        top.addWidget(self.bell)
        lay.addLayout(top)

        self.title = QLabel(game.title)
        self.title.setWordWrap(True)
        _theme.style(self.title, "GAME_TITLE")
        lay.addWidget(self.title)
        if live:
            stop = game.start_utc + usual_length
            self.bar = ProgressBar(elapsed_pct(game.start_utc, stop, now), height=6)
            self.bar.setToolTip(f"Started {fmt_time(game.start_utc)} · usually ends about {fmt_time(stop)}")
            lay.addWidget(self.bar)
        else:
            self.bar = None
        league = QLabel(game.league)
        _theme.style(league, "TEXT_SM_MUTED")
        lay.addWidget(league)

        # The play line: what a click (or a double-click on the card) plays.
        playing = next((f for f in game.playable if f.channel_id == playing_id), None)
        self.top_feed = playing or (game.playable[0] if game.playable else None)
        line = self.play_line = PlayLine(live)
        line.clicked.connect(self._play_top)
        pl = QHBoxLayout(line)
        pl.setContentsMargins(4, 2, 4, 2)
        pl.setSpacing(5)
        if live:
            mark = QLabel()
            _theme.style(mark, "GAME_PLAYING_NAME" if playing else "GAME_LIVE_TAG")
            _icon_utils.set_label_icon(mark, "play", 12)
            pl.addWidget(mark)
            if playing:
                word = QLabel("PLAYING")
                _theme.style(word, "GAME_PLAYING")
                pl.addWidget(word)
            line.setToolTip("Click to play on this channel (double-clicking the card does the same)")
        else:
            line.setToolTip("This channel plays the game once it starts")
        if self.top_feed is not None:
            if self.top_feed.region:
                pl.addWidget(make_region_chip(self.top_feed.region))
            self.station = QLabel(self.top_feed.station)
            self.station.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            _theme.style(self.station, "CHANNEL_NAME_LIVE" if live else "TEXT_SM_MUTED")
            pl.addWidget(self.station, 1)
        others = len(game.playable) - 1
        self.more_chip = None
        if others > 0:
            # The live-channel mark + "+N": more channels, not a score (owner, SV-Q32).
            self.more_chip = make_chip(f"+{others}", selected=expanded)
            _icon_utils.set_button_icon(self.more_chip, "live")
            self.more_chip.setToolTip("Hide the other channels" if expanded
                                      else f"Show the {others} other channels showing this game")
            self.more_chip.clicked.connect(lambda: self.toggled.emit(self.game))
            pl.addWidget(self.more_chip)
        lay.addWidget(line)

        if expanded and channels is not None:
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            _theme.style(sep, "SEPARATOR_LINE")
            sep.setMaximumHeight(1)
            lay.addWidget(sep)
            lay.addWidget(channels)

    def _play_top(self) -> None:
        if self.top_feed is not None and self.top_feed.channel_id and self.state != UPCOMING:
            self.play.emit(self.top_feed.channel_id)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt API)
        self._play_top()
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self.state not in (ON_NOW, ENDING):
            return
        menu = QMenu(self)
        menu.addAction("Mark as finished").triggered.connect(lambda: self.finished.emit(self.game))
        menu.exec(event.globalPos())
