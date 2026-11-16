"""Settings → System Tray: close to the tray, and which alerts reach the system.

Its own page at the owner's request ("might as well be its own section",
2026-11-16), and its own module because ``settings_dialog_tabs.py`` is at its
code-health ceiling. ``SettingsDialog._load_values``/``_save_values`` read and
write the widgets; ``_apply_tray_setting`` (``settings_apply.HANDLERS``) shows
or removes the icon after OK.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QCheckBox, QGroupBox, QLabel, QVBoxLayout, QWidget

from streamselect.gui.tray import tray_available

#: Shown in place of the setting where the desktop has no tray (TQ12).
NO_TRAY_TEXT = "This desktop has no system tray, so closing the window quits StreamSelect."


class SettingsTrayTabMixin:
    """The System Tray page builder, mixed into ``SettingsDialog``."""

    def _build_tray_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)
        layout.setContentsMargins(12, 12, 12, 12)
        has_tray = tray_available()

        tray_group = QGroupBox("System Tray")
        tray_layout = QVBoxLayout(tray_group)
        tray_layout.setSpacing(8)
        self._tray_close_check = QCheckBox("Keep StreamSelect in the system tray when its window is closed")
        self._tray_close_check.setToolTip(
            "On: closing the window leaves StreamSelect running in the tray (the menu bar\n"
            "on macOS), still checking your alerts and updates. Quit from the tray's menu\n"
            "or File ▸ Exit.\n"
            "Off: closing the window quits StreamSelect.")
        self._tray_close_check.setEnabled(has_tray)
        tray_layout.addWidget(self._tray_close_check)
        if not has_tray:
            note = QLabel(NO_TRAY_TEXT)
            note.setWordWrap(True)
            tray_layout.addWidget(note)
        layout.addWidget(tray_group)

        notify_group = QGroupBox("System notifications")
        notify_layout = QVBoxLayout(notify_group)
        notify_layout.setSpacing(8)
        notify_layout.addWidget(QLabel("While StreamSelect is in the tray, show a system notification for:"))
        self._tray_notify_watch_check = QCheckBox("Watch Alerts")
        self._tray_notify_watch_check.setToolTip(
            "A programme matching your Watch Alerts is about to start, or a\n"
            "monitored series has new episodes.")
        self._tray_notify_games_check = QCheckBox("Game alerts")
        self._tray_notify_games_check.setToolTip(
            "A game you set an alert on in Sports is about to start, or has started.")
        self._tray_notify_updates_check = QCheckBox("Updates")
        self._tray_notify_updates_check.setToolTip("A new version of StreamSelect is available.")
        for check in (self._tray_notify_watch_check, self._tray_notify_games_check,
                      self._tray_notify_updates_check):
            check.setEnabled(has_tray)
            notify_layout.addWidget(check)
        layout.addWidget(notify_group)

        layout.addStretch()
        return tab

    def _load_tray_values(self, c) -> None:
        self._tray_close_check.setChecked(c.tray_close_to_tray is True)
        self._tray_notify_watch_check.setChecked(c.tray_notify_watch)
        self._tray_notify_games_check.setChecked(c.tray_notify_games)
        self._tray_notify_updates_check.setChecked(c.tray_notify_updates)

    def _save_tray_values(self, c) -> None:
        # Unticked while never asked stays "never asked", so the first close still asks (TQ1).
        if self._tray_close_check.isChecked() or c.tray_close_to_tray is not None:
            c.tray_close_to_tray = self._tray_close_check.isChecked()
        c.tray_notify_watch = self._tray_notify_watch_check.isChecked()
        c.tray_notify_games = self._tray_notify_games_check.isChecked()
        c.tray_notify_updates = self._tray_notify_updates_check.isChecked()
