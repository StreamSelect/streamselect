"""MainWindow: keep running in the system tray when the window is closed.

Settled in the "Tray Mode" design (owner, 2026-11-16, TQ1-TQ14). The tray
icon and its menu are :class:`~streamselect.gui.tray.TrayController`; this
mixin is the window's half: what a close does, showing and hiding, and quitting.

Only a close the USER starts goes to the tray — the window's close button,
Alt+F4, Cmd+W — which Qt marks as spontaneous. File ▸ Exit, the updater's
restart and Fresh start call ``close()`` from code and still quit, as does
Quit in the tray menu (``quit_app``).
"""

from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox

from streamselect.gui import macos_dock
from streamselect.gui.main_window_nav import CONTENT_VIEW_ATTRS
from streamselect.gui.tray import TrayController, tray_available

#: The automatic update check is re-asked this often while the app runs; its own
#: 24 h throttle decides whether GitHub is actually asked (TQ10).
UPDATE_RECHECK_MS = 60 * 60_000


class _TrayMixin:
    """Close-to-tray, show/hide from the tray, and quit."""

    def _setup_tray(self) -> None:
        """Build the tray icon when the desktop has a tray (TQ12); else nothing."""
        self._update_recheck = QTimer(self)
        self._update_recheck.setInterval(UPDATE_RECHECK_MS)
        self._update_recheck.timeout.connect(self.update_checker.check_async)
        self._update_recheck.start()
        if not tray_available():
            self.tray = None
            return
        self.tray = TrayController(self, parent=self)
        self.notification_manager.system_sink = self.tray.notify
        self._register_cleanable("tray", self._shutdown_tray)
        self._apply_tray_setting()

    def _apply_tray_setting(self) -> None:
        """Show the icon while close-to-tray is on (a ``settings_applied`` handler)."""
        tray = self.__dict__.get("tray")
        on = tray is not None and self.config.tray_close_to_tray is True
        if tray is not None:
            tray.set_visible(on)
        # A hidden window must not quit the app when a dialog it opened closes.
        QApplication.instance().setQuitOnLastWindowClosed(not on)

    def _close_to_tray(self, event) -> bool:
        """Called first by ``closeEvent``: True when the close became a hide."""
        tray = self.__dict__.get("tray")
        if tray is None or not event.spontaneous():
            return False
        if self.config.tray_close_to_tray is None:
            answer = self._ask_close_to_tray()
            if answer is None:              # dismissed: neither, so stay open
                event.ignore()
                return True
            self.config.tray_close_to_tray = answer
            self.config.save()
            self._apply_tray_setting()
        if not self.config.tray_close_to_tray:
            return False
        event.ignore()
        self.hide_to_tray()
        return True

    def _ask_close_to_tray(self) -> bool | None:
        """The one-time question on the first close (TQ1): keep running, quit, or neither."""
        box = QMessageBox(self)
        box.setWindowTitle("Keep StreamSelect running?")
        box.setText("Keep StreamSelect running in the system tray?")
        box.setInformativeText(
            "It keeps checking your Watch Alerts, game alerts and updates, and tells you "
            "with a system notification. You can change this in Settings ▸ System Tray.")
        keep = box.addButton("Keep running", QMessageBox.ButtonRole.AcceptRole)
        quit_ = box.addButton("Quit", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(keep)
        box.exec()
        clicked = box.clickedButton()
        if clicked is keep:
            return True
        if clicked is quit_:
            return False
        return None

    def _views_on_screen(self) -> list:
        """The content views showing now that have a lifecycle (timers, loads)."""
        views = [self.__dict__.get(attr) for attr in CONTENT_VIEW_ATTRS]
        views += list(self.__dict__.get("explore_views", {}).values())
        # getattr is polymorphism here, as in _hide_all_content_views: the list
        # mixes ContentViews with plain item views that have no lifecycle.
        return [v for v in views if v is not None and v.isVisible()
                and getattr(v, "on_deactivate", None) and getattr(v, "on_activate", None)]

    def hide_to_tray(self) -> None:
        """Hide the window, pausing the view on screen; the first time, say where it went.

        A hidden window's view would otherwise keep its timers: the guide went on
        re-reading On Now every minute with nobody looking.
        """
        # Asked BEFORE hiding: once the window is hidden no view is "visible".
        self._paused_views = self._views_on_screen()
        for view in self._paused_views:
            view.on_deactivate()
        self.hide()
        macos_dock.show_in_dock(False)
        if not self.config.tray_hide_notice_shown:
            self.tray.message("StreamSelect is still running",
                              "It's in the tray. Use Quit in its menu to close it completely.")
            self.config.tray_hide_notice_shown = True
            self.config.save()
        self.tray.rebuild()

    def show_from_tray(self, target: str | None = None) -> None:
        """Bring the window back, on *target* (a ``navigate_to`` string) when given."""
        macos_dock.show_in_dock(True)
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()
        paused, self._paused_views = self.__dict__.get("_paused_views", []), []
        # Navigating activates the view it lands on; otherwise resume the paused one.
        if not (target and self.navigate_to(target)):
            for view in paused:
                view.on_activate()
        tray = self.__dict__.get("tray")
        if tray is not None:
            tray.mark_seen()
            tray.rebuild()

    def toggle_from_tray(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide_to_tray()
        else:
            self.show_from_tray()

    def quit_app(self) -> None:
        """Quit for real: a close from code is not spontaneous, so it is not hidden."""
        if self.close():
            QApplication.instance().quit()

    def _shutdown_tray(self) -> None:
        """Cleanup: remove the icon; the close was accepted, so the app quits."""
        self.notification_manager.system_sink = None
        self.tray.shutdown()
        app = QApplication.instance()
        if not app.quitOnLastWindowClosed():
            # The window may have been hidden, where closing it quits nothing.
            app.setQuitOnLastWindowClosed(True)
            QTimer.singleShot(0, app.quit)
