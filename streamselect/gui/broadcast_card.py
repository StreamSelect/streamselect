"""A broadcast on now that names its league but not its teams (design "Other Broadcasts On Now").

Half the height of a game card and as wide (OB-Q4), on the deepest background
(OB-Q5). Top to bottom: LIVE and since when, then where the title came from,
GUIDE or NAME (OB-Q6/Q7); the title as listed; a thin bar only when the guide
gives a stop time (OB-Q8, a channel name states no end); and the game card's
play line — a guide programme's channel, or a channel's package — with "+N"
opening the other channels (OB-Q10/Q11).
"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from streamselect.core.epg_utils import fmt_time
from streamselect.core.games.broadcasts import BroadcastDTO
from streamselect.gui import cursor_affordance, icons
from streamselect.gui import icon_utils as _icon_utils
from streamselect.gui import theme as _theme
from streamselect.gui.badge_utils import make_region_chip
from streamselect.gui.detail_chips import make_chip
from streamselect.gui.game_card import CARD_WIDTH, PlayLine
from streamselect.gui.progress_paint import ProgressBar, elapsed_pct

GUIDE_WORD, NAME_WORD = "GUIDE", "NAME"


class BroadcastCard(QFrame):
    """See the module docstring. ``play`` carries a channel id."""

    play = pyqtSignal(str)

    def __init__(self, item: BroadcastDTO, now: datetime, *, meta: str = "", parent=None):
        super().__init__(parent)
        self.item = item
        self.setObjectName("broadcastCard")
        _theme.style(self, "BROADCAST_CARD")
        self.setFixedWidth(CARD_WIDTH)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 7, 12, 7)
        lay.setSpacing(3)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        self.tag = QLabel(f"{icons.status_dot_icon} LIVE")
        _theme.style(self.tag, "GAME_LIVE_TAG")
        top.addWidget(self.tag)
        since = QLabel(f"since {fmt_time(item.start_utc)}")
        _theme.style(since, "TEXT_SM_MUTED")
        top.addWidget(since)
        top.addStretch(1)
        self.source = QLabel(GUIDE_WORD if item.from_guide else NAME_WORD)
        self.source.setToolTip("Title from the channel guide" if item.from_guide
                               else "Title from the channel's name")
        _theme.style(self.source, "TEXT_SM_MUTED")
        top.addWidget(self.source)
        lay.addLayout(top)

        self.title = QLabel(item.title)
        self.title.setToolTip(item.title + (f"\n{meta}" if meta else ""))
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        _theme.style(self.title, "PANEL_BODY")
        lay.addWidget(self.title)
        if meta:                         # By time: "Sport · League" (OB-Q15)
            m = QLabel(meta)
            _theme.style(m, "TEXT_SM_MUTED")
            lay.addWidget(m)

        self.bar = None
        if item.stop_utc is not None:
            self.bar = ProgressBar(elapsed_pct(item.start_utc, item.stop_utc, now), height=3)
            self.bar.setToolTip(f"On {fmt_time(item.start_utc)}–{fmt_time(item.stop_utc)}, by the guide")
            lay.addWidget(self.bar)

        first = item.channels[0]
        line = self.play_line = PlayLine(True)
        line.clicked.connect(lambda: self.play.emit(first.channel_id))
        line.setToolTip(f"Click to play\n{first.name}\n{first.collection}")
        pl = QHBoxLayout(line)
        pl.setContentsMargins(4, 2, 4, 2)
        pl.setSpacing(5)
        mark = QLabel()
        _theme.style(mark, "GAME_LIVE_TAG")
        _icon_utils.set_label_icon(mark, "play", 12)
        pl.addWidget(mark)
        if first.region:
            pl.addWidget(make_region_chip(first.region))
        self.station = QLabel(first.station)
        self.station.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        _theme.style(self.station, "CHANNEL_NAME_LIVE")
        pl.addWidget(self.station, 1)
        self.more_chip = None
        self.others = None
        if len(item.channels) > 1:
            n = len(item.channels) - 1
            self.more_chip = make_chip(f"+{n}", selected=False)
            _icon_utils.set_button_icon(self.more_chip, "live")
            self.more_chip.setToolTip(f"Show the {n} other channels showing this")
            self.more_chip.clicked.connect(self._toggle_others)
            pl.addWidget(self.more_chip)
        lay.addWidget(line)

    def _toggle_others(self) -> None:
        """Open or close the other channels, as rows under the play line."""
        if self.others is None:
            self.others = QWidget()
            v = QVBoxLayout(self.others)
            v.setContentsMargins(0, 2, 0, 0)
            v.setSpacing(0)
            for ch in self.item.channels[1:]:
                row = QPushButton(f"[{ch.region}] {ch.station}" if ch.region else ch.station)
                row.setToolTip(f"Click to play\n{ch.name}\n{ch.collection}")
                _theme.style(row, "GAME_FEED_ROW")
                cursor_affordance.set_clickable(row)
                row.clicked.connect(lambda _=False, cid=ch.channel_id: self.play.emit(cid))
                v.addWidget(row)
            self.layout().addWidget(self.others)
            self.others.setVisible(False)
        opened = not self.others.isVisible()
        self.others.setVisible(opened)
        n = len(self.item.channels) - 1
        self.more_chip.setToolTip("Hide the other channels" if opened else f"Show the {n} other channels showing this")

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        """Elide the title and station to the card's width (a long guide title stays one line)."""
        super().resizeEvent(event)
        for label, text in ((self.title, self.item.title), (self.station, self.item.channels[0].station)):
            label.setText(label.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight,
                                                         max(40, label.width())))
