"""MainWindow mixin — the update notice, the install hand-off, the Tools items.

The notice stays on screen until the user picks one of its four answers:

* **Now**: on macOS and Windows, download the update, start the helper that
  swaps it in (``core/update_installer.py``) and quit; the helper starts the
  new version. Where the app can't replace itself (Linux, a source run, a
  read-only install folder) it opens the download page instead; a Mac that
  can't swap still gets the old assisted download of the ``.dmg``.
* **Later**: close the notice. The next automatic check, a day later at the
  earliest, asks again.
* **Skip**: don't mention this version again.
* **Never**: turn automatic checks off. Tools ▸ Check for Updates
  Automatically turns them back on.

All Qt work stays here on the main thread; the checker and the installer have
no widgets in them.
"""

from __future__ import annotations

from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtGui import QAction, QDesktopServices
from loguru import logger

from streamselect.core import runtime_env, update_installer
from streamselect.gui import icon_utils as _icon_utils

_RELEASES_PAGE = "https://github.com/StreamSelect/streamselect/releases/latest"
# Long enough to read "Restarting…" before the window closes.
_QUIT_DELAY_MS = 1500


class _UpdatesMixin:
    """Main-thread slots for the :class:`UpdateChecker` signal surface."""

    def _wire_update_checker(self) -> None:
        checker = self.update_checker
        checker.update_available.connect(self._on_update_available)
        checker.no_update.connect(self._on_update_none)
        checker.download_completed.connect(self._on_update_downloaded)
        checker.install_progress.connect(self._on_update_install_progress)
        checker.install_ready.connect(self._on_update_install_ready)
        checker.install_failed.connect(self._on_update_install_failed)

    # -- the notice -----------------------------------------------------------

    def _on_update_available(self, info) -> None:
        """Show the update notice; it stays until one of its answers is picked."""
        old = getattr(self, "_update_notice_id", None)
        if old:
            self.notification_manager.dismiss(old)
        self._update_notice_id = self.notification_manager.show(
            title=f"StreamSelect {info.latest} is available",
            message=f"You have {info.current}. Update?",
            type="info",
            dismissible=False,
            actions=[
                ("Now", lambda i=info: self._update_now(i)),
                ("Later", lambda: None),
                ("Skip", lambda i=info: self._skip_update_version(i)),
                ("Never", self._never_check_for_updates),
            ],
        )

    def _on_update_none(self, info) -> None:
        """Manual check finished with nothing newer (info) or an error (None)."""
        if info is None:
            self.notification_manager.show(
                title="Couldn't check for updates",
                message="No network, or GitHub is unreachable. Try again later.",
                type="warning",
                auto_dismiss_ms=6000,
            )
        else:
            self.notification_manager.show(
                title="You're up to date",
                message=f"StreamSelect {info.current} is the latest version.",
                type="success",
                auto_dismiss_ms=5000,
            )

    # -- Now ------------------------------------------------------------------

    def _update_now(self, info) -> None:
        """Install in place where possible; otherwise fall back (module docstring)."""
        target = update_installer.install_target()
        if update_installer.can_self_update(target):
            self._update_progress_id = self.notification_manager.show_progress(
                f"Downloading StreamSelect {info.latest}…", total=100
            )
            self.update_checker.install_async(info, target)
        elif info.dmg_url and runtime_env.is_macos():
            self._start_update_download(info)
        else:
            QDesktopServices.openUrl(QUrl(info.release_url or _RELEASES_PAGE))

    def _on_update_install_progress(self, percent: int) -> None:
        notice = getattr(self, "_update_progress_id", None)
        if notice:
            self.notification_manager.update_progress(notice, percent, total=100)

    def _on_update_install_ready(self, paths) -> None:
        """The new version is staged: start the helper, then quit so it can swap."""
        target, staged = paths
        notice = getattr(self, "_update_progress_id", None)
        try:
            update_installer.launch_helper(target, staged)
        except update_installer.UpdateInstallError as exc:
            self._on_update_install_failed(str(exc))
            return
        if notice:
            self.notification_manager.update(
                notice, title="Restarting to finish the update…", message="",
            )
        QTimer.singleShot(_QUIT_DELAY_MS, self.close)

    def _on_update_install_failed(self, message: str) -> None:
        notice = getattr(self, "_update_progress_id", None)
        if notice:
            self.notification_manager.dismiss(notice)
            self._update_progress_id = None
        logger.warning(f"Update install failed: {message}")
        self.notification_manager.show(
            title="Couldn't install the update",
            message=f"{message} You can download it from the release page instead.",
            type="error",
            dismissible=True,
            actions=[("Open the download page",
                      lambda: QDesktopServices.openUrl(QUrl(_RELEASES_PAGE)))],
        )

    # -- assisted .dmg download (a Mac that can't replace its own app) --------

    def _start_update_download(self, info) -> None:
        """Save the ``.dmg`` to Downloads; ``_on_update_downloaded`` opens it."""
        self.notification_manager.show(
            title="Downloading update…",
            message="Saving the new StreamSelect to your Downloads folder.",
            type="info",
            auto_dismiss_ms=4000,
        )
        self.update_checker.download_update(info)

    def _on_update_downloaded(self, path: str) -> None:
        """Open the downloaded ``.dmg`` (mounts it on macOS) or report failure."""
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            self.notification_manager.show(
                title="Update downloaded",
                message=f"Saved to {path}. Open it and drag StreamSelect into Applications.",
                type="success",
                auto_dismiss_ms=8000,
            )
        else:
            logger.warning("Update download failed; opening releases page")
            self.notification_manager.show(
                title="Download failed",
                message="Could not download the update. Opening the releases page.",
                type="error",
                auto_dismiss_ms=6000,
            )
            QDesktopServices.openUrl(QUrl(_RELEASES_PAGE))

    # -- Skip / Never ---------------------------------------------------------

    def _save_update_config(self) -> None:
        try:
            self.config.save()
        except Exception as exc:  # pragma: no cover - best-effort persistence
            logger.debug(f"Could not persist update settings: {exc}")

    def _skip_update_version(self, info) -> None:
        """Record the skipped version so the automatic notice stops for it."""
        self.config.update_skip_version = info.latest
        self._save_update_config()
        self.notification_manager.show(
            title=f"Skipping {info.latest}",
            message="You won't be asked about this version again.",
            type="info",
            auto_dismiss_ms=5000,
        )

    def _never_check_for_updates(self) -> None:
        """Turn automatic checks off (the Tools menu turns them back on)."""
        self._set_update_checks_enabled(False)
        self.notification_manager.show(
            title="Automatic update checks are off",
            message="Turn them back on from Tools ▸ Check for Updates Automatically.",
            type="info",
            auto_dismiss_ms=8000,
        )

    def _set_update_checks_enabled(self, enabled: bool) -> None:
        self.config.update_check_enabled = bool(enabled)
        self._save_update_config()

    # -- Tools menu -----------------------------------------------------------

    def _add_update_menu_items(self, tools_menu) -> None:
        """Tools ▸ Software Update… and the automatic-check toggle."""
        check = QAction(_icon_utils.role_icon("software_update"), "Software &Update…", self)
        check.setToolTip("Check now for a newer version of StreamSelect")
        check.triggered.connect(self._manual_update_check)
        tools_menu.addAction(check)
        auto = self._update_auto_action = QAction(
            "Check for Updates Automatically", self, checkable=True
        )
        auto.setToolTip(
            "Once a day, look for a newer version when StreamSelect starts. "
            "Unticked is the same as answering Never to the update notice."
        )
        auto.setChecked(bool(getattr(self.config, "update_check_enabled", True)))
        auto.toggled.connect(self._set_update_checks_enabled)
        tools_menu.addAction(auto)
        # Settings and the notice's Never change the same value; re-read it
        # each time the menu opens rather than chase every writer.
        tools_menu.aboutToShow.connect(self._sync_update_menu)

    def _sync_update_menu(self) -> None:
        auto = self._update_auto_action
        auto.blockSignals(True)
        auto.setChecked(bool(getattr(self.config, "update_check_enabled", True)))
        auto.blockSignals(False)

    def _manual_update_check(self) -> None:
        """Run a manual check (bypasses the enable/throttle/skip gates)."""
        self.notification_manager.show(
            title="Checking for updates…",
            type="info",
            auto_dismiss_ms=3000,
        )
        self.update_checker.check_async(manual=True)
