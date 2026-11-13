"""Tell the user when an event they set an alert on is about to start, and when it starts.

Polls every 30 s (a cheap read of stored games and event rules, off the UI
thread through the host's ``_run_query``); the decision is
``core.games.alerts.due_notices`` and the lead time is
``Config.event_alert_lead_minutes`` (Sports Desk SV-Q43). Each notice offers
Play, which plays the channel the event's card would play.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer

from streamselect.core.epg_utils import now_utc
from streamselect.core.games.alerts import due_notices, expired_event_rules, load_alerts, remove_alerts
from streamselect.core.games.read import arrange_feeds, best_feed, load_games, load_watch_history
from streamselect.core.games.store import sport_settings
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
        self._host._run_query(query, self._on_data, commit=True)

    def _on_data(self, result) -> None:
        games, alerts, history = result if result else ([], [], {})
        if not alerts:
            return
        config = self._host.config
        for key, game, title in due_notices(games, alerts, self._clock(),
                                            int(config.event_alert_lead_minutes), self._sent):
            self._sent.add(key)
            game = arrange_feeds(game, config.game_channel_prefs.get(game.league_key, {}), history,
                                 self._clock())
            feed = best_feed(game)
            where = f" · plays on {feed.region + ' ' if feed.region else ''}{feed.station}" if feed else ""
            actions = [("Play", lambda cid=feed.channel_id: self._play(cid))] if feed else []
            self._host.notification_manager.show(
                title=title, message=f"{game.title} · {game.league}{where}",
                type="info", auto_dismiss_ms=60_000, actions=actions)
