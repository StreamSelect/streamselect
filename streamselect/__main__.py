"""Main entry point for StreamSelect application"""

import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from loguru import logger

from streamselect.core.runtime_env import bundle_resource_path, flatpak_app_id, is_windows
from streamselect.core.app_logging import configure_logging

from streamselect.gui import cursor_affordance
from streamselect.gui import theme as _theme
from streamselect.gui import ui_phase as _phase
from streamselect.gui.main_window import MainWindow
from streamselect.core.config import Config
from streamselect.core.url_policy import UrlRankingPolicy, set_url_ranking_policy


def setup_logging():
    """Configure application logging"""
    configure_logging()

    # Name the build in the FIRST line, not just the About dialog. Under
    # rolling releases every push ships, so "0.56.0" no longer identifies a
    # build — a pasted log has to say which commit produced it or a report
    # about it cannot be checked out. User report: "shouldn't the console log state
    # which version of StreamSelect is being launched? it's kind of weird to omit
    # that".
    #
    # Reuses the identity the title bar already shows rather than composing a
    # second one, so the window and the log can never disagree about which build
    # is running. window_title() resolves to "StreamSelect (branch sha)" in a checkout
    # and "StreamSelect 0.56.0+20260829.a3e7a28" in a packaged build, where the stamped
    # id names the exact commit; the version rides alongside because the branch
    # form does not carry it.
    from streamselect import __version__
    from streamselect.core.build_info import window_title

    logger.info(f"{window_title()} starting — v{__version__}")


def main():
    """Main application entry point"""
    # A packaged build's refresh worker is this same executable started by
    # multiprocessing; freeze_support() runs it and exits before any UI is built.
    import multiprocessing
    multiprocessing.freeze_support()
    setup_logging()

    # A fresh start (Tools menu) recorded by the previous run: wipe BEFORE the
    # config or the database is opened. Returns the sources to re-add, if kept.
    from streamselect.core import fresh_start
    kept_sources = fresh_start.perform()

    # Load configuration (returns tuple: config, recovered_from_backup)
    config, recovered_from_backup = Config.load()

    # Save config to create .yaml file and backup on first startup
    try:
        config.save()
    except Exception as e:
        logger.error(f"Failed to save config on startup: {e}")

    # Resolve the provider-URL ranking knobs ONCE, here, from the loaded config.
    # Provider.ordered_urls() reads the resolved policy rather than a Config —
    # the six busiest cycling call sites live in providers/xtream.py, which has
    # no Config access by design. Without this line the three url_* settings are
    # decorative: everything falls back to defaults and editing config.yaml does
    # nothing.
    set_url_ranking_policy(UrlRankingPolicy.from_config(config))

    # Create Qt application
    app = QApplication(sys.argv)
    # The window and task-switcher icon. There was none earlier —
    # packaging/streamselect.spec carried `icon=None, # placeholder omitted for the
    # MVP`, and nothing called setWindowIcon, so every surface fell back to
    # the window manager's generic square.
    _icon = bundle_resource_path("packaging/icon/streamselect-256.png")
    if _icon.exists():
        app.setWindowIcon(QIcon(str(_icon)))
    else:
        logger.warning("App icon missing at {} — falling back to the system default", _icon)
    app.setApplicationName("StreamSelect")
    app.setOrganizationName("StreamSelect")
    # Inside the Flatpak, name the exported desktop file so Wayland compositors
    # match the window to StreamSelect's icon instead of a generic one.
    if flatpak_app_id():
        app.setDesktopFileName(flatpak_app_id())
    # Windows' native styles (windowsvista / windows11) draw many controls
    # themselves and ignore the QPalette that theme.apply_theme() sets as the
    # floor for every widget without its own stylesheet — a dark theme would
    # come up with light native controls. Fusion honours the palette, which is
    # what Linux typically runs already. macOS keeps its native style.
    if is_windows():
        app.setStyle("Fusion")

    # Bundled typefaces (streamselect/assets/fonts) — registered before the theme and
    # before any widget, because the type scale sets SIZES and inherits the
    # family from the application font. A face that fails to load is logged and
    # the platform default stands; it must not cost the app its launch.
    from streamselect.gui import fonts as _fonts
    _fonts.apply_ui_font(app)

    # Pointing-hand cursor on hover for clickable controls (single app-level
    # event filter; kept referenced on the app so it isn't garbage-collected).
    app._cursor_affordance_filter = cursor_affordance.install(app)

    # Apply the user's saved theme BEFORE any widget/window is constructed —
    # both the design-token layer (every ``theme.COLOR_*``/semantic constant
    # widgets read while building their stylesheets) and the QPalette floor
    # (streamselect/gui/theme.py's qt_palette(), an earlier change) so a cold launch on a
    # non-default theme renders correctly end-to-end, not just after a live
    # Settings round-trip via MainWindow.apply_configured_theme().
    _theme.apply_theme(config.theme_name)

    # Create and show main window. Both are phases: the gap between "Main
    # window initialized" and the first channel query is where a ~3s stall has
    # been read off log gaps for three sessions, and a gap is not evidence.
    with _phase.phase("startup.MainWindow"):
        window = MainWindow(config, config_recovered=recovered_from_backup)
    with _phase.phase("startup.show"):
        window.show()
    if kept_sources:
        window.restore_sources(kept_sources)

    # Run application
    code = app.exec()
    # Delete the window now rather than inside PyQt's exit-time cleanup, which
    # segfaults on a live window with many children (GUARD-7, gui/app_exit.py).
    from streamselect.gui.app_exit import release_before_exit
    release_before_exit(window)
    if fresh_start.pending():
        fresh_start.relaunch()      # the new process performs the wipe
    sys.exit(code)


if __name__ == "__main__":
    main()
