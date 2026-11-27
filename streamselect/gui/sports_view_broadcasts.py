"""The Sports view's "Other broadcasts on now" (design "Other Broadcasts On Now", rev 2).

Mixed into :class:`~streamselect.gui.sports_view.SportsView`. On now's header
carries a Games | All track (OB-Q3, search's All | Word: All includes Games) when
the league has broadcasts on air that name it but not their teams; All adds them
at the bottom of On now in their own section, as half-height cards. All is the
default and the choice is one setting for every league, remembered (OB-Q17/Q18);
a league with none on air shows no track (OB-Q19).
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from streamselect.core import sports_catalog
from streamselect.gui import theme as _theme
from streamselect.gui.broadcast_card import BroadcastCard
from streamselect.gui.chips import ToggleChip
from streamselect.gui.flow_layout import FlowLayout

#: The remembered choice in ``Config.sports_view_state``.
STATE_KEY = "other_broadcasts"


class SportsBroadcastsMixin:
    """See the module docstring. The host supplies ``_state``, ``_save``, ``_render``,
    ``_header``, ``_folded``, ``_on_now_section``, ``_layout`` and ``playRequested``."""

    _broadcasts: list

    @property
    def show_broadcasts(self) -> bool:
        return bool(self._state().get(STATE_KEY, True))

    def _set_show_broadcasts(self, on: bool) -> None:
        if on != self.show_broadcasts:
            self._state()[STATE_KEY] = bool(on)
            self._save()
            QTimer.singleShot(0, self._render)

    def _broadcasts_of(self, league_key: Optional[str] = None) -> list:
        return [b for b in self._broadcasts if league_key is None or b.league_key == league_key]

    def _broadcast_track(self, n: int) -> QWidget:
        """On now's Games | All track, built like the app's view switcher."""
        track = QWidget()
        track.setObjectName("onNowTrack")
        _theme.style_fn(track, lambda: (
            f"#onNowTrack {{ background: {_theme.COLOR_BG_CARD}; border: 1px solid {_theme.COLOR_BORDER};"
            f" border-radius: {ToggleChip.SEGMENT_RADIUS + 1}px; }}"))
        h = QHBoxLayout(track)
        h.setContentsMargins(0, 0, 0, 0)    # zero: the cells share the track's edges
        h.setSpacing(0)
        shown = self.show_broadcasts
        self.games_chip = ToggleChip("Games", enabled=not shown, segment="first")
        self.games_chip.setToolTip("On now shows the games only")
        self.all_chip = ToggleChip("All", enabled=shown, segment="last")
        self.all_chip.setToolTip(f"Also show the {n} broadcasts on now that name the league but not the teams")
        self.games_chip.clicked.connect(lambda: self._set_show_broadcasts(False))
        self.all_chip.clicked.connect(lambda: self._set_show_broadcasts(True))
        h.addWidget(self.games_chip)
        h.addWidget(self.all_chip)
        return track

    def _on_now_and_broadcasts(self, key: str, on_now: list, now: datetime, items: list, *,
                               meta: Callable, sub: int = 0, card_meta: Callable = lambda b: "") -> None:
        """On now, with its track, then "Other broadcasts on now" when All is chosen."""
        controls = self._broadcast_track(len(items)) if items else None
        if on_now:
            self._on_now_section(key, on_now, now, meta=meta, sub=sub, controls=controls)
        elif items:              # no game on, but broadcasts: the header still carries the track
            self._layout.addWidget(self._header(key, "On now", None, foldable=False, sub=sub,
                                                controls=controls))
            if not self.show_broadcasts:
                note = QLabel(f"No games on now · {len(items)} other broadcasts (All shows them)")
                _theme.style(note, "TEXT_SM_MUTED")
                self._layout.addWidget(note)
        if not items or not self.show_broadcasts:
            return
        other = key.rsplit(":", 1)[0] + ":other_broadcasts"
        self._layout.addWidget(self._header(other, "Other broadcasts on now", len(items), foldable=True,
                                            what="the list of other broadcasts on now", sub=sub))
        if other in self._folded():
            return
        host = QWidget()
        grid = FlowLayout(host, spacing=8, centre=True)
        for b in items:
            card = BroadcastCard(b, now, meta=card_meta(b))
            card.play.connect(self.playRequested)
            grid.addWidget(card)
        self._layout.addWidget(host)

    @staticmethod
    def _broadcast_label(b) -> str:
        """By time: the card names its sport and league (OB-Q15)."""
        return f"{sports_catalog.sport_label(b.sport)} · {b.league}"
