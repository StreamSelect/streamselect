"""The Sports view's headers: a sport's header and a league's banner.

Split from ``sports_view.py`` (2026-11-18) when the league chips became controls:
each chip in a sport's header shows or hides its league in the list below (owner,
2026-11-18: "the chip toggle is just for tidying the view"). Hiding is this view
only — the games are still found, alerted and counted elsewhere — and is
remembered in ``Config.sports_view_state["hidden_leagues"]``. A hidden chip is
dashed and greyer and keeps its live mark, so a game on now is never missed.
"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from streamselect.core.epg_utils import fmt_time
from streamselect.core.games.alerts import alerts_for
from streamselect.core.games.read import event_is_live as event_live
from streamselect.gui import cursor_affordance
from streamselect.gui import icon_utils as _icon_utils
from streamselect.gui import theme as _theme
from streamselect.gui.chip_row import CHIP_COUNT, chip_widget, labeled_chip
from streamselect.gui.similar_lightbox_card import _ClickableFrame

#: ``Config.sports_view_state`` key: the leagues hidden from the list, "sport/league".
HIDDEN_LEAGUES = "hidden_leagues"


def league_key(sport: str, league: str) -> str:
    return f"{sport}/{league}"


def _bell(px: int = 11) -> QLabel:
    """The bell of a set alert, in its colour (SIDEBAR_CHIP_GROUP's chipAlert)."""
    bell = QLabel()
    bell.setProperty("chipAlert", "true")
    _icon_utils.set_label_icon(bell, "alert", px)
    return bell


def add_alert_mark(chip: QWidget, alerted: int) -> QLabel:
    """Append a bell and how many have an alert set to a ``labeled_chip``; returns
    that count (the chip's own live mark and count, if any, stay as they are)."""
    bell = _bell()
    count = QLabel(str(alerted))
    count.setProperty("chipCount", "true")
    lay = chip.layout()
    lay.addWidget(bell)
    lay.addWidget(count)
    count.bell = bell
    return count


def alert_count_chip(total: int, alerted: int) -> QWidget:
    """A collapsed list's count when some of its games have an alert set:
    "12 (bell) 1", the bell in a set alert's colour (owner, 2026-11-18)."""
    chip = labeled_chip(str(total))
    chip.count_label = add_alert_mark(chip, alerted)
    chip.icon_label = chip.count_label.bell
    chip.setToolTip(f"{total} game{'s' if total != 1 else ''}, {alerted} with an alert set")
    return chip


class _LeagueToggle(QFrame):
    """A league chip as a control: a click toggles the league and is taken here,
    so it never reaches the sport header under it (which would fold the sport)."""

    clicked = pyqtSignal()

    def __init__(self, chip: QWidget) -> None:
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(chip)
        cursor_affordance.set_clickable(self)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        event.accept()
        self.clicked.emit()


class SportsHeadersMixin:
    """The sport header and league banner of :class:`~streamselect.gui.sports_view.SportsView`."""

    @property
    def hidden_leagues(self) -> set[str]:
        """The leagues hidden from the list ("sport/league")."""
        return set(self._state().get(HIDDEN_LEAGUES, []))

    def shown_games(self, games: list) -> list:
        """*games* without those of hidden leagues."""
        hidden = self.hidden_leagues
        return [g for g in games if league_key(g.sport, g.league) not in hidden] if hidden else list(games)

    def _message_line(self, text: str) -> None:
        """A muted line in the list (every league of a sport hidden)."""
        line = QLabel(text)
        line.setObjectName("allLeaguesHidden")
        _theme.style(line, "TEXT_SM_MUTED")
        self._layout.addWidget(line)

    def _toggle_league(self, sport: str, league: str) -> None:
        hiding = league_key(sport, league) not in self.hidden_leagues
        self._state()[HIDDEN_LEAGUES] = sorted(self.hidden_leagues ^ {league_key(sport, league)})
        self._save()
        self._render()
        if hiding:
            self.leagueHidden.emit(sport, league)

    def _league_banner(self, key: str, league: str, games: list, now: datetime) -> QWidget:
        """A league's name, larger, centred between two rules, with its logo and a
        chip: how many games, and how many are on now — or, with none on, when the
        next starts ("14 (•) 7:00 PM", owner 2026-11-18). Folds the league."""
        band = _ClickableFrame()
        cursor_affordance.set_clickable(band)
        band.setToolTip(f"{'Expand' if key in self._folded() else 'Collapse'} the {league} games list")
        band.clicked.connect(lambda k=key: self._toggle_fold(k))
        h = QHBoxLayout(band)
        h.setContentsMargins(0, 12, 0, 0)
        h.setSpacing(10)

        def rule() -> QWidget:
            line = QWidget()
            line.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            line.setFixedHeight(1)
            _theme.style(line, "FOOTER_DIVIDER")
            return line
        h.addWidget(rule(), 1, Qt.AlignmentFlag.AlignVCenter)
        caret = QLabel()
        _icon_utils.set_label_icon(caret, "expand" if key in self._folded() else "collapse", 12)
        h.addWidget(caret)
        logo = self._league_logo(next((g.league_logo for g in games if g.league_logo), ""))
        if logo is not None and not logo.isNull():
            mark = QLabel()
            mark.setPixmap(logo.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation))
            h.addWidget(mark)
        title = QLabel(league)
        _theme.style(title, "LEAGUE_TITLE")
        h.addWidget(title)
        # Finished games don't count: nobody cares (owner, 2026-11-18).
        on_now, later, _ = self._split(games, now)
        ahead = len(on_now) + len(later)
        nxt = fmt_time(min(g.start_utc for g in later)) if later else ""
        chip = labeled_chip(str(ahead), len(on_now) or nxt, "live")
        chip.setToolTip(f"{league}: {ahead} game{'s' if ahead != 1 else ''} on now or still to come"
                        + (f", {len(on_now)} on now" if on_now else f", next at {nxt}" if nxt else ""))
        chip.setVisible(ahead > 0)
        # Collapsed, the chip also says how many have an alert set (owner, 2026-11-18):
        # "13 (•) 1 (bell) 2".
        alerted = sum(1 for g in [g for g, _s in on_now] + later if alerts_for(g, self._alerts))
        band.alert_label = None
        if key in self._folded() and alerted:
            band.alert_label = add_alert_mark(chip, alerted)
            chip.setToolTip(chip.toolTip() + f", {alerted} with an alert set")
        h.addWidget(chip)
        h.addWidget(rule(), 1, Qt.AlignmentFlag.AlignVCenter)
        band.title, band.chip = title, chip
        self.headers[key] = band
        return band

    def _sport_header(self, sport: str, games: list) -> QWidget:
        """The sport's own header: its name and how many games, then on the right a
        chip per league with games (with how many are on now) that shows or hides
        that league; the rest of the band folds the segment."""
        key = f"sport:{sport}"
        # The whole band folds, not just the name (owner report: only the word worked).
        band = _ClickableFrame()
        cursor_affordance.set_clickable(band)
        band.setToolTip(f"{'Expand' if key in self._folded() else 'Collapse'} every {sport.title()} list")
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
        # Every game on now or still to come, all leagues (owner, 2026-11-18): the
        # headings' outlined count chip, not clickable, so a click still folds.
        # A hidden league's games are not counted: the count matches the list.
        shown = self.shown_games(games)
        on_now, later, _ = self._split(shown, self._clock()) if sport in self.sports else ([], [], [])
        count = chip_widget(CHIP_COUNT, str(len(on_now) + len(later)))
        count.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        count.setToolTip(f"{len(on_now) + len(later)} {sport} games on now or still to come")
        count.setVisible(bool(on_now or later))
        h.addWidget(count)
        band.count = count
        # Collapsed, it says how many of those have an alert set, as a collapsed
        # day does: "12 (bell) 1" (owner, 2026-11-18). Open, the rows show it.
        ahead = [g for g, _state in on_now] + later
        alerted = sum(1 for g in ahead if alerts_for(g, self._alerts))
        band.alert_chip = None
        if key in self._folded() and alerted:
            band.alert_chip = alert_count_chip(len(ahead), alerted)
            h.insertWidget(h.indexOf(count) + 1, band.alert_chip)
            count.hide()
        # One outlined chip per league with games here — none when nothing is
        # listed — and a league with games on now carries the live mark and how
        # many (owner, 2026-11-17: "when there are live games within a league
        # they get the logo and #").
        # The league chips stand apart on the right (owner, 2026-11-18): each shows or
        # hides its league in the list below; the rest of the band folds the sport.
        h.addStretch(1)
        settings = self.sports.get(sport)
        now = self._clock()
        hidden = self.hidden_leagues
        for league in self._league_order(sport, games):
            on = sum(1 for g in games if g.league == league and settings is not None
                     and event_live(g, now, settings))
            chip = labeled_chip(league, on, "live")
            off = league_key(sport, league) in hidden
            chip.setProperty("off", "true" if off else "false")
            toggle = _LeagueToggle(chip)
            toggle.setToolTip(f"{'Show' if off else 'Hide'} the {league} games")
            toggle.clicked.connect(lambda sp=sport, lg=league: self._toggle_league(sp, lg))
            h.addWidget(toggle)
            self.league_chips[(sport, league)] = chip
        self.headers[key] = band
        return band
