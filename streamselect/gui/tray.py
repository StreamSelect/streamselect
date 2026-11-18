"""The system-tray icon: its menu, its tooltip, and the system notifications.

Settled in the "Tray Mode" design (owner, 2026-11-16, TQ1-TQ14). The menu is
rebuilt from what is known at that moment: the player's windows (what plays),
the event-alert notifier's latest poll (alerted games) and a read of the guide
for Watch Alert matches, refreshed off-thread every few minutes. Nothing here
talks to a source: idling adds no network use (TQ10).

System notifications arrive through ``NotificationManager.system_sink`` — one
seam, so no sender knows the tray exists — and go out only while the window is
hidden or minimised (TQ5), only for the kinds switched on in Settings → System
Tray, and never while paused (TQ7).
"""

from __future__ import annotations

from loguru import logger
from PyQt6.QtCore import QObject, QPointF, QRect, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from streamselect.core import runtime_env, tray_state, watchlist
from streamselect.core.epg_utils import now_utc
from streamselect.gui import theme
from streamselect.gui.icon_utils import role_icon, role_pixmap

#: How often the guide's Watch Alert matches and the tooltip are re-read.
REFRESH_MS = 5 * 60_000
#: How long a system notification stays up, where the system lets the app say.
MESSAGE_MS = 10_000

#: Settings switch per notification kind.
_KIND_SWITCH = {
    tray_state.KIND_WATCH: "tray_notify_watch",
    tray_state.KIND_GAME: "tray_notify_games",
    tray_state.KIND_UPDATE: "tray_notify_updates",
}

_PAUSES = (
    (tray_state.PAUSE_HOUR, "For 1 hour"),
    (tray_state.PAUSE_TOMORROW, "Until tomorrow"),
    (tray_state.PAUSE_INDEFINITE, "Until I turn them back on"),
)


#: Sizes the badged icon is drawn at; trays pick the nearest.
_BADGE_SIZES = (16, 22, 24, 32, 48, 64)


#: Each badge's glyph and disc colour (``tray_state.BADGE_*``).
_BADGES = {
    # Live draws the logo itself on this colour (live_icon); the glyph is unused.
    tray_state.BADGE_LIVE: ("sports", "COLOR_TRAY_LIVE"),
    # The Watch Alerts bell on a soft disc: a red "!" was too aggressive for
    # "something you follow is on" (owner, 2026-11-16).
    tray_state.BADGE_ALERT: ("tray_alert_badge", "COLOR_TRAY_ALERT"),
    tray_state.BADGE_UPDATE: ("tray_update_badge", "COLOR_TRAY_UPDATE"),
}


def _glyph_disc(p: QPainter, disc: QRect, glyph: str, fill: str, share: float) -> None:
    """A *fill* disc with *glyph* at *share* of its width, in its on-fill colour."""
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(fill))
    p.drawEllipse(disc)
    glyph_px = max(6, round(disc.width() * share))
    mark = QRect(0, 0, glyph_px, glyph_px)
    mark.moveCenter(disc.center())
    p.drawPixmap(mark, role_pixmap(glyph, theme.on_fill(fill), glyph_px))


#: The corner badge's width as a share of the icon. It was 0.55: at a 22 px
#: tray that is a 12 px disc with a 10 px glyph, merged into the logo (owner,
#: 2026-11-17: "should the notification alert be so small").
BADGE_SHARE = 0.68


def badged_icon(base: QIcon, glyph: str = "tray_alert_badge",
                fill_token: str = "COLOR_TRAY_ALERT") -> QIcon:
    """*base* with a *glyph* on a disc in its lower-right corner.

    The app's own icon stays recognisable, so the tray is still easy to find
    (owner, 2026-11-16: a generic notification icon made it hard to spot). A
    transparent ring is cut out of the logo around the disc, so the badge reads
    as its own shape on any panel colour instead of merging into the logo.
    """
    out = QIcon()
    fill = getattr(theme, fill_token)
    for size in _BADGE_SIZES:
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        base.paint(p, QRect(0, 0, size, size))
        d = max(10, round(size * BADGE_SHARE))
        disc = QRect(size - d, size - d, d, d)
        ring = max(1, round(size / 16))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0))
        p.drawEllipse(disc.adjusted(-ring, -ring, ring, ring))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        _glyph_disc(p, disc, glyph, fill, 0.8)
        p.end()
        out.addPixmap(pm)
    return out


def _logo_paths() -> tuple[QPainterPath, QPainterPath]:
    """The app logo's S-arrow in its own 64-unit box, transcribed from
    ``packaging/icon/streamselect.svg``: the S (stroked 8 wide) and the arrowhead."""
    s = QPainterPath(QPointF(12, 48))
    s.lineTo(40, 48)
    s.arcTo(QRectF(32, 32, 16, 16), 270, 180)       # round the right, up to (40, 32)
    s.lineTo(24, 32)
    s.arcTo(QRectF(16, 16, 16, 16), 270, -180)      # round the left, up to (24, 16)
    s.lineTo(36, 16)
    head = QPainterPath(QPointF(36, 5.5))
    head.lineTo(53, 16)
    head.lineTo(36, 26.5)
    head.closeSubpath()
    return s, head


def live_icon(fill_token: str = "COLOR_TRAY_LIVE") -> QIcon:
    """The tray icon while an alerted game is live: the app logo on *fill*.

    A corner badge is too small to notice at tray size for something on NOW
    (owner, 2026-11-17), and a whistle in place of the logo "shifts away from
    the logo" — so the logo itself turns green: its S-arrow, in the on-fill
    colour, on a *fill* square with the logo's own corners. The plain logo
    returns when the game ends; the tooltip and menu still name the game.
    """
    out = QIcon()
    fill = QColor(getattr(theme, fill_token))
    ink = QColor(theme.on_fill(getattr(theme, fill_token)))
    s_path, head = _logo_paths()
    for size in _BADGE_SIZES:
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(size / 64, size / 64)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fill)
        p.drawRoundedRect(QRectF(0, 0, 64, 64), 14, 14)
        pen = QPen(ink, 8)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(s_path)
        pen = QPen(ink, 2)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(ink)
        p.drawPath(head)
        p.end()
        out.addPixmap(pm)
    return out


def _item_icon(item: tray_state.TrayItem) -> str:
    """A game wears the Sports whistle, so it never reads as one more guide match."""
    if item.kind == tray_state.KIND_GAME:
        return "sports"
    return "play" if item.plays else "monitor"


def tray_available() -> bool:
    """Whether this desktop shows tray icons (stock GNOME does not, TQ12)."""
    return QSystemTrayIcon.isSystemTrayAvailable()


class TrayController(QObject):
    """Owns the tray icon. *host* is the main window (``_TrayMixin``)."""

    def __init__(self, host, parent=None, *, clock=now_utc):
        super().__init__(parent)
        self._host = host
        self._clock = clock
        self._watch_items: list[tray_state.TrayItem] = []
        self._message_target: str | None = None
        self._plain_icon = QApplication.windowIcon()
        self._badge_icons = {badge: (live_icon(token) if badge == tray_state.BADGE_LIVE
                                     else badged_icon(self._plain_icon, glyph, token))
                             for badge, (glyph, token) in _BADGES.items()}
        #: Notification kinds sent since the menu or window was last opened.
        self._unseen: set[str] = set()
        self._badge: str | None = None
        self._icon = QSystemTrayIcon(self._plain_icon, self)
        self._menu = QMenu()
        self._menu.aboutToShow.connect(self.mark_seen)
        self._menu.aboutToShow.connect(self.rebuild)
        self._icon.setContextMenu(self._menu)
        self._icon.activated.connect(self._on_activated)
        self._icon.messageClicked.connect(self._on_message_clicked)
        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self.refresh)
        # A game going live changes the badge between menu opens; the notifier
        # is built first (``catalog_refresh_tick``) and says when it re-reads.
        notifier = host.__dict__.get("event_alert_notifier")
        if notifier is not None:
            notifier.updated.connect(self.refresh_icon)

    # -- lifecycle ------------------------------------------------------------

    def set_visible(self, visible: bool) -> None:
        """Show or remove the icon; the refresh runs only while it is shown."""
        self._icon.setVisible(visible)
        if visible:
            self._timer.start()
            self.refresh()
        else:
            self._timer.stop()

    def is_visible(self) -> bool:
        return self._icon.isVisible()

    def shutdown(self) -> None:
        self._timer.stop()
        self._icon.hide()

    # -- what the menu knows -------------------------------------------------

    def playing(self) -> dict[str, str]:
        """``{player window: title}`` for every stream still playing."""
        return self._host.player_manager.playing_titles()

    def sections(self) -> list[tuple[str, list[tray_state.TrayItem]]]:
        """Alerted games, then Watch Alert matches, as the menu lists them."""
        notifier = self._host.__dict__.get("event_alert_notifier")
        games = list(notifier.upcoming) if notifier is not None else []
        return tray_state.menu_sections(games + self._watch_items, self._clock())

    def refresh(self) -> None:
        """Re-read the guide's Watch Alert matches off-thread, then redraw."""
        rules = watchlist.rules(self._host.config)
        if not rules:
            self._watch_items = []
            self.rebuild()
            return
        hours = int(tray_state.HORIZON.total_seconds() // 3600)

        def query(repos):
            from streamselect.core.repositories.epg import EpgRepository
            from streamselect.core.database import ChannelDB

            providers = repos.providers.get_epg_active_provider_ids()
            if not providers:
                return []
            hidden = set(repos.providers.get_hidden_provider_ids())
            repo = EpgRepository(repos.session)
            found = []
            for live, data in (
                (True, repo.get_live_for_watchlist(
                    rules, provider_ids=providers, excluded_channel_provider_ids=hidden)),
                (False, repo.get_upcoming_for_watchlist(
                    rules, hours_ahead=hours, provider_ids=providers,
                    excluded_channel_provider_ids=hidden)),
            ):
                for progs in data.values():
                    found.extend((live, p.title, p.start_time, p.channel_db_id) for p in progs)
            ids = {cid for *_, cid in found if cid}
            names = dict(repos.session.query(ChannelDB.id, ChannelDB.detected_title)
                         .filter(ChannelDB.id.in_(ids)).all()) if ids else {}
            return [tray_state.TrayItem(start, title, names.get(cid) or "", "view:epg",
                                        live=live, channel_id=cid or None)
                    for live, title, start, cid in found]

        self._host._run_query(query, self._on_watch_items,
                              on_error=lambda exc: logger.warning("Tray: guide read failed: {}", exc))

    def _on_watch_items(self, items) -> None:
        self._watch_items = list(items or [])
        self.rebuild()

    # -- menu and tooltip -----------------------------------------------------

    def rebuild(self) -> None:
        """Rebuild the menu and tooltip from what is known now."""
        now = self._clock()
        playing = [t for t in self.playing().values() if t]
        sections = self.sections()
        count = sum(len(items) for _heading, items in sections)
        pause = tray_state.pause_text(self._host.config.tray_notifications_paused, now)
        self._icon.setToolTip(tray_state.tooltip(count, playing, pause))

        self.refresh_icon()
        m = self._menu
        m.clear()
        shown = self._host.isVisible() and not self._host.isMinimized()
        m.addAction("Hide StreamSelect" if shown else "Show StreamSelect", self._host.toggle_from_tray)
        if self.playing():
            m.addSection("Playing")
            for title in self.playing().values():
                m.addAction(role_icon("play"), title or "A stream", self._host.show_from_tray)
            m.addAction(role_icon("stop_playback"), "Stop playback", self.stop_playback)
        for heading, items in sections:
            m.addSection(heading)
            for item in items:
                m.addAction(role_icon(_item_icon(item)), item.label(), lambda i=item: self.open_item(i))
        if not sections:
            m.addSection("Your alerts")
            m.addAction("Nothing alerted in the next 12 hours").setEnabled(False)
        m.addSeparator()
        sub = m.addMenu(role_icon("monitor_off"), "Pause notifications")
        if pause:
            sub.addAction(pause).setEnabled(False)
            sub.addAction("Resume notifications", lambda: self.set_pause(""))
            sub.addSeparator()
        for choice, label in _PAUSES:
            sub.addAction(label, lambda c=choice: self.set_pause(c))
        m.addAction(role_icon("software_update"), "Check for Updates…",
                    self._host._manual_update_check)
        m.addSeparator()
        m.addAction("Quit StreamSelect", self._host.quit_app)

    def open_item(self, item: tray_state.TrayItem) -> None:
        """Open the app on *item*; a LIVE one also starts playing (owner, 2026-11-16)."""
        self._host.show_from_tray(item.target)
        if item.plays:
            self._host.play_channel_by_id(item.plays)
        QTimer.singleShot(500, self.rebuild)

    def stop_playback(self) -> None:
        """Stop every player window, each through ``PlayerManager`` (TQ9)."""
        for key in list(self.playing()):
            self._host.player_manager.stop(key=key)
        QTimer.singleShot(500, self.rebuild)

    def set_pause(self, choice: str) -> None:
        """Pause for *choice* (``tray_state`` PAUSE_*), or resume with ""."""
        value = tray_state.pause_value(choice, self._clock()) if choice else ""
        self._host.config.tray_notifications_paused = value
        self._host.config.save()
        self.rebuild()

    # -- clicks ---------------------------------------------------------------

    def _on_activated(self, reason) -> None:
        # macOS opens the menu on a click, as menu-bar items do (TQ4).
        if runtime_env.is_macos():
            return
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._host.toggle_from_tray()

    def _on_message_clicked(self) -> None:
        self._host.show_from_tray(self._message_target)

    @property
    def unseen(self) -> bool:
        """Whether a notification was sent since the menu or window was opened."""
        return bool(self._unseen)

    def mark_seen(self) -> None:
        """The menu or the window was opened: the notices are seen."""
        self._unseen.clear()
        self.refresh_icon()

    def refresh_icon(self) -> None:
        """Wear the badge ``tray_state.badge_for`` picks, or the plain icon."""
        notifier = self._host.__dict__.get("event_alert_notifier")
        live = notifier is not None and any(i.live for i in notifier.upcoming)
        badge = tray_state.badge_for(live, self._unseen)
        if badge != self._badge:
            self._badge = badge
            self._icon.setIcon(self._badge_icons.get(badge, self._plain_icon))

    # -- system notifications -------------------------------------------------

    def wants(self, kind: str) -> bool:
        """Whether a *kind* notification goes to the system right now."""
        config = self._host.config
        if not self.is_visible() or kind not in _KIND_SWITCH or not getattr(config, _KIND_SWITCH[kind]):
            return False
        if tray_state.paused_until(config.tray_notifications_paused, self._clock()) is not None:
            return False
        return not self._host.isVisible() or self._host.isMinimized()

    def notify(self, notification) -> None:
        """``NotificationManager.system_sink``: send it on when :meth:`wants` says so."""
        if not self.wants(notification.alert):
            if notification.alert:
                logger.info("Tray: {} alert stays in the app (window open, paused or switched off): {}",
                            notification.alert, notification.title)
            return
        logger.info("Tray: {} alert sent to the system: {}", notification.alert, notification.title)
        self.message(notification.title, notification.message, notification.open_target or None,
                     alert=notification.alert)

    def message(self, title: str, body: str, target: str | None = None, *,
                alert: str | None = None) -> None:
        """Show a system notification; a click on it opens *target*.

        An *alert* (its ``tray_state.KIND_*``) badges the tray icon until the menu
        or the window is opened.
        The icon is passed as a QIcon, never a ``MessageIcon`` type: on KDE Qt
        shows the type's theme icon ("dialog-information") in place of the
        app's while the notification is up, which made the tray hard to find.
        """
        # Qt reports a click on the latest message only, so the latest target wins.
        self._message_target = target
        if alert:
            self._unseen.add(alert)
            self.refresh_icon()
        self._icon.showMessage(title, body, self._icon.icon(), MESSAGE_MS)
