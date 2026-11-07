"""The content area's empty state: one panel above every view, one decision.

Mixed into :class:`~streamselect.gui.main_window.MainWindow`. The panel
(``empty_state.EmptyStatePanel``) sits in ``_list_layout`` above all the
content views, so the two states about the SOURCES — none usable, or the first
ones still loading — show in every view at once without each view knowing
(user report: "every view shows a proper empty state at zero sources … hide
nothing"). The channel list adds its own three (nothing here, no results,
filtered) through ``_set_list_empty_state``; those show only while the list is.

``_sync_empty_state`` is the only thing that shows or hides the panel. It runs
when the sources change (``_sync_no_source_notice``), when the list's result
changes, and when the list or the Sources screen is shown or hidden — the
panel never sits over the Sources screen, where the user is fixing the cause.
Watching those two widgets' Show/Hide replaces the old banner's habit of being
hidden by every view switch (``_hide_all_content_views``), which is how the
zero-sources banner went missing at launch.
"""
from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QEvent, QObject, QTimer

from streamselect.gui.empty_state import EmptyState, EmptyStatePanel, empty_state_text


class _ShowHideWatcher(QObject):
    """Calls *on_change* whenever a watched widget is shown or hidden."""

    def __init__(self, parent: QObject, on_change: Callable[[], None]) -> None:
        super().__init__(parent)
        self._on_change = on_change

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt API)
        if event.type() in (QEvent.Type.Show, QEvent.Type.Hide):
            self._on_change()
        return False


class _EmptyStateMixin:
    """Builds the content area's empty-state panel and decides what it says."""

    def _build_empty_state_panel(self) -> None:
        """Called once from ``setup_ui``, where the zero-sources banner was built."""
        self._empty_state_panel = EmptyStatePanel()
        self._list_layout.addWidget(self._empty_state_panel)
        # The views it watches are built later in setup_ui.
        QTimer.singleShot(0, self._watch_views_for_empty_state)

    def _watch_views_for_empty_state(self) -> None:
        # Parented to the panel: it lives exactly as long as what it serves.
        watcher = _ShowHideWatcher(self._empty_state_panel, self._sync_empty_state)
        for name in ("channels_list", "sources_manager_view"):
            widget = self.__dict__.get(name)
            if widget is not None:
                widget.installEventFilter(watcher)
        self._empty_state_watcher = watcher
        self._sync_empty_state()

    def _set_list_empty_state(self, state: EmptyState | None = None, **detail) -> None:
        """The channel list's own empty result (or None when it has rows)."""
        self._list_empty_state = (state, detail) if state else None
        self._sync_empty_state()

    def _current_empty_state(self) -> tuple[str, str, str | None] | None:
        """What the panel should say now, most fundamental cause first."""
        manager = self.__dict__.get("sources_manager_view")
        if manager is not None and manager.isVisible():
            return None
        avail = self.__dict__.get("_source_availability")
        if avail is not None and not avail.usable:
            return empty_state_text(EmptyState.NO_SOURCE, avail=avail)
        loading = self.__dict__.get("_first_loading") or {}
        if loading and avail is not None and len(loading) >= avail.usable:
            return empty_state_text(EmptyState.FIRST_LOAD, names=list(loading.values()))
        listed = self.__dict__.get("_list_empty_state")
        channels = self.__dict__.get("channels_list")
        if listed and channels is not None and channels.isVisible():
            state, detail = listed
            if state is EmptyState.NOTHING_HERE and avail is not None:
                detail = {**detail, "sources": avail.usable}
            return empty_state_text(state, **detail)
        return None

    def _sync_empty_state(self) -> None:
        """Show, re-word or hide the panel — the only place that does."""
        panel = self.__dict__.get("_empty_state_panel")
        if panel is None:
            return
        text = self._current_empty_state()
        if text is None:
            panel.hide()
            return
        headline, hint, action = text
        panel.show_state(headline, hint, self._empty_state_actions(action))

    def _empty_state_actions(self, action: str | None) -> list[tuple[str, Callable]]:
        if action == "add":
            return [("Add Source", self.add_provider)]
        if action == "open":
            return [("Open Sources", self.switch_to_sources_manager)]
        if action == "clear_search":
            return [("Clear search", self.search_input.clear)]
        return []
