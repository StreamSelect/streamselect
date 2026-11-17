"""Tell the user when an event they set an alert on is about to start, and when it starts.

Polls every 30 s (a cheap read of stored games and event rules, off the UI
thread through the host's ``_run_query``); the decision is
``core.games.alerts.due_notices`` and the lead time is
``Config.event_alert_lead_minutes`` (Sports Desk SV-Q43). Each notice offers
Play, which plays the channel the event's card would play.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer
from loguru import logger

from streamselect.core.epg_utils import now_utc
from streamselect.core.games.alerts import due_notices, expired_event_rules, load_alerts, remove_alerts
from streamselect.core.games.read import (ON_NOW, ENDING, arrange_feeds, best_feed, game_state,
                                          load_games, load_watch_history)
from streamselect.core.games.store import sport_settings
from streamselect.core.tray_state import KIND_GAME, TrayItem
from streamselect.core.repositories.provider import ProviderRepository

POLL_MS = 30_000


class EventAlertNotifier(QObject):
    """Owns the poll; ``play`` is the host's play-by-channel-id slot."""

    def __init__(self, host, play, parent=None, *, clock=now_utc):
        super().__init__(parent)
        self._host = host
        self._play = play
        self._clock = clock
        self._sent: set[str] = set()
        #: The alerted games from the latest poll, for the tray menu ("Tray Mode" TQ3).
        self.upcoming: list[TrayItem] = []
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self.check)

    def start(self) -> None:
        self._timer.start()

    def shutdown(self) -> None:
        self._timer.stop()

    def check(self) -> None:
        now = self._clock()
        sports = list(sport_settings())

        def query(repos):
            alerts = load_alerts(repos.session)
            # A one-event rule outlives its event by nothing useful: delete it here,
            # on the poll that already reads the rules.
            gone = expired_event_rules(alerts, now)
            if gone:
                remove_alerts(repos.session, gone)
                alerts = [a for a in alerts if a.id not in gone]
            if not alerts:
                return [], [], {}
            hidden = set(ProviderRepository(repos.session).get_hidden_provider_ids())
            games = [g for sp in sports for g in load_games(repos.session, sp, hidden, 1, 2)]
            return games, alerts, load_watch_history(repos.session)
        # A failed read or rule clean-up is logged; the next poll (30 s) tries again.
        self._host._run_query(query, self._on_data, commit=True,
                              on_error=lambda exc: logger.warning("Event alerts: check failed: {}", exc))

    def _on_data(self, result) -> None:
        games, alerts, history = result if result else ([], [], {})
        config = self._host.config
        now = self._clock()

        def arranged(game):
            return arrange_feeds(game, config.game_channel_prefs.get(game.league_key, {}), history, now)
        self.upcoming = alerted_items(games, alerts, now, arranged)
        if not alerts:
            return
        for key, game, title in due_notices(games, alerts, self._clock(),
                                            int(config.event_alert_lead_minutes), self._sent):
            self._sent.add(key)
            game = arranged(game)
            feed = best_feed(game)
            logger.info("Event alert: {} — {} ({})", title, game.title, game.league)
            where = f" · plays on {feed.region + ' ' if feed.region else ''}{feed.station}" if feed else ""
            actions = [("Play", lambda cid=feed.channel_id: self._play(cid))] if feed else []
            self._host.notification_manager.show(
                title=title, message=f"{game.title} · {game.league}{where}",
                type="info", auto_dismiss_ms=60_000, actions=actions,
                alert="game", open_target="view:sports")


def alerted_items(games, alerts, now, arranged=lambda g: g) -> list[TrayItem]:
    """The games an alert matches, as tray menu items; live ones marked LIVE.

    A live game carries the feed a click plays: the first of *arranged* (the
    user's preferred collection first, as on its card).
    """
    settings = sport_settings()
    out = []
    for game in games:
        if not any(a.matches(game) for a in alerts):
            continue
        state = game_state(game, now, settings[game.sport]) if game.sport in settings else ""
        if state not in (ON_NOW, ENDING) and game.start_utc < now:
            continue                     # over, or past its usual length
        live = state in (ON_NOW, ENDING)
        feed = best_feed(arranged(game)) if live else None
        out.append(TrayItem(game.start_utc, game.matchup, game.league, "view:sports",
                            live=live, channel_id=feed.channel_id if feed else None,
                            kind=KIND_GAME))
    return out
