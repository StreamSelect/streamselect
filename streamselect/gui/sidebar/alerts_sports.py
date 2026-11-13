"""The Watch Alerts "Sports" group: events you set an alert on, upcoming or live.

One row per event (two games between the same teams on back-to-back days are
two rows), drawn with the EPG group's own row (``_AlertRow``), so a live event
shows the same progress bar and an upcoming one the same time to its start. No
``+1`` pill: the bar or the time is what a row says (owner, 2026-11-13).

An event leaves by itself — when it is over, marked finished, or watched — and
the rule that matched it stays (``core.games.alerts.waiting_events``). Sits
directly under EPG because both are time-bound (owner).

A mixin like the section's other groups: it holds no state of its own beyond the
widgets ``_build_sports_group`` makes, reached through ``self``.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QHBoxLayout, QListWidgetItem, QWidget

from streamselect.core.epg_utils import is_local_today, now_utc, to_local
from streamselect.core.games.alerts import load_alerts, waiting_events, watched_game_ids
from streamselect.core.games.read import (
    UPCOMING, GameDTO, arrange_feeds, best_feed, game_state, load_games, load_watch_history,
)
from streamselect.core.games.store import sport_settings
from streamselect.core.repositories.provider import ProviderRepository
from streamselect.gui.relative_time import humanize_remaining, humanize_until
from streamselect.gui.sidebar.alerts_rows import _AlertRow
from streamselect.gui.sidebar.base import GroupHeading

#: How often the group re-reads its events: a start, an end or a watch changes membership.
SPORTS_POLL_MS = 60_000


def _live_end(game: GameDTO, now, settings):
    """The end a live row's bar counts down to: the sport's usual length, then its long limit."""
    end = game.start_utc + settings.usual_length
    return end if now < end else game.start_utc + settings.long_limit


class SportsGroupMixin:
    """Builds, loads and draws the Sports group; wired from ``WatchAlertsSection``."""

    def _build_sports_group(self) -> None:
        """The heading and list, added to the section's content layout (called from
        ``create_content`` right after the EPG group)."""
        self._sports_collapsed = False
        self._sports_games: list[GameDTO] = []
        self._sports_rows: list[tuple[_AlertRow, GameDTO]] = []
        row = QHBoxLayout()
        row.setContentsMargins(0, 2, 0, 1)
        row.setSpacing(4)
        self._sports_toggle = GroupHeading(
            "Sports", interactive=True,
            tooltip=("Events you set an alert on with the Sports bell, upcoming or live. "
                     "Each one goes by itself once it is over or you start watching it. "
                     "Click to collapse or expand"),
        )
        self._sports_toggle.clicked.connect(self._toggle_sports_group)
        row.addWidget(self._sports_toggle)
        row.addStretch()
        self._sports_hdr_container = QWidget()
        self._sports_hdr_container.setLayout(row)
        self._sports_hdr_container.hide()
        self.content_layout.addWidget(self._sports_hdr_container)

        self._sports_list = self._make_group_list()
        self._sports_list.itemDoubleClicked.connect(self._on_sports_double_clicked)
        self.content_layout.addWidget(self._sports_list)

        self._sports_timer = QTimer(self)
        self._sports_timer.setInterval(SPORTS_POLL_MS)
        self._sports_timer.timeout.connect(self.refresh_sports)
        self._sports_timer.start()
        QTimer.singleShot(0, self.refresh_sports)

    # ── data ─────────────────────────────────────────────────────────────
    def refresh_sports(self) -> None:
        """Re-read the alerted events off the UI thread (the section's own executor)."""
        executor = self.__dict__.get("_executor")
        if executor is None or self.db is None:
            return
        settings = sport_settings()

        def work():
            try:
                with self.db.session_scope(commit=False) as session:
                    alerts = load_alerts(session)
                    if not alerts:
                        return [], {}
                    hidden = set(ProviderRepository(session).get_hidden_provider_ids())
                    games = [g for sp in settings for g in load_games(session, sp, hidden, 1, 2)]
                    waiting = waiting_events(games, alerts, now_utc(), settings,
                                             watched_game_ids(session, games))
                    return waiting, (load_watch_history(session) if waiting else {})
            except Exception:  # noqa: BLE001 — a failed read keeps the last rows
                return None
        try:
            future = executor.submit(work)
        except RuntimeError:        # the section is shutting down
            return
        future.add_done_callback(lambda f: self._sports_ready.emit(f.result()))

    def _on_sports_ready(self, result) -> None:
        if result is None:
            return
        games, history = result
        now = now_utc()
        prefs = getattr(self.config, "game_channel_prefs", {}) or {}
        self._sports_games = [arrange_feeds(g, prefs.get(g.league_key, {}), history, now) for g in games]
        self._render_sports()

    # ── drawing ──────────────────────────────────────────────────────────
    def _render_sports(self) -> None:
        games = self._sports_games
        self._sports_list.clear()
        self._sports_rows = []
        self._sports_toggle.set_count(len(games) or None)
        self._sports_toggle.set_news(len(games) if self._sports_collapsed else 0)
        self._sports_hdr_container.setVisible(bool(games))
        self._sports_list.setVisible(bool(games) and not self._sports_collapsed)
        if games and not self._sports_collapsed:
            settings = sport_settings()
            now = now_utc()
            for g in games:
                self._add_sports_row(g, settings[g.sport], now)
            QTimer.singleShot(0, self.reapply_row_budget)
        self._recompute_empty()
        self.refresh_header_status()

    def _add_sports_row(self, game: GameDTO, settings, now) -> None:
        live = game_state(game, now, settings) != UPCOMING
        feed = best_feed(game)
        if live:
            when = _live_end(game, now, settings)
            text = humanize_remaining(when, now)
        else:
            when = game.start_utc
            text = humanize_until(when, now, to_local=to_local, is_local_today=is_local_today)
        row = _AlertRow(game.title, text, self.config, when=when, live=live,
                        started_at=game.start_utc if live else None,
                        region=feed.region if feed else "",
                        bar_source=feed.station if feed else "", marker_column=False)
        cid = feed.channel_id if feed else ""
        row.play_clicked.connect(lambda c=cid: c and self.alertClicked.emit(c))
        row.row_clicked.connect(lambda c=cid: c and self.channel_selected.emit(c))
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, cid)
        where = f"\nPlays on {feed.region + ' ' if feed.region else ''}{feed.station}" if feed else ""
        item.setToolTip(f"{game.title} · {game.league}{where}\nDouble-click to play")
        self._sports_list.addItem(item)
        item.setSizeHint(row.sizeHint())
        self._sports_list.setItemWidget(item, row)
        self._sports_rows.append((row, game))

    def _toggle_sports_group(self) -> None:
        self._sports_collapsed = not self._sports_collapsed
        self._render_sports()

    def _on_sports_double_clicked(self, item: QListWidgetItem) -> None:
        cid = item.data(Qt.ItemDataRole.UserRole)
        if cid:
            self.alertClicked.emit(cid)

    # ── the section's shared tick and play marker ────────────────────────
    def _tick(self) -> None:
        super()._tick()
        if self.__dict__.get("is_collapsed") or not self.__dict__.get("_sports_rows"):
            return
        now = now_utc()
        for row, _game in self._sports_rows:
            row.refresh_time(now)

    def set_playing(self, channel_id: str | None) -> None:
        super().set_playing(channel_id)
        for row, game in self.__dict__.get("_sports_rows", ()):
            row.set_playing(bool(channel_id) and any(f.channel_id == channel_id for f in game.playable))

    def sports_waiting(self) -> int:
        """How many alerted events are waiting — the header's sports badge."""
        return len(self.__dict__.get("_sports_games", ()))

