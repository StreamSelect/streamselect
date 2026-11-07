"""Provider editor — the four tab shells and the Settings tab's General group.

Mixed into :class:`~streamselect.gui.provider_editor.ProviderEditorView`. Each tab is
wrapped in its own scroll area (``_wrap_scroll``) so tall content scrolls
independently. What goes IN each tab lives with the job it does:

  * Summary    — Account Info: ``provider_editor_account``.
  * Connection — credentials and server addresses: ``provider_editor_addresses``.
  * Settings   — General (auto-refresh, adult flag) here; the guide (EPG)
                 group: ``provider_editor_guide``.
  * Analytics  — the per-source analytics view, built on first open.

The persistent Delete / Test Connection / Discard / Save Changes footer lives
OUTSIDE the ``QTabWidget`` (built by ``provider_editor.py``) — it applies to
the whole source, not to a single tab. Test Connection itself is
``provider_editor_connection_test``; adding a new source is
``provider_editor_new``.
"""
from __future__ import annotations



from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QFrame, QGroupBox, QLabel,
    QScrollArea, QVBoxLayout, QWidget,
)

from streamselect.core.repositories import RepositoryFactory
from streamselect.gui import theme as _theme




class _VerticalScroll(QScrollArea):
    """A vertical-only scroll area that reports its content's minimum WIDTH.

    With the horizontal bar off, a plain ``QScrollArea`` advertises a small
    minimum whatever its content needs, so the editor claimed it fit in less
    room than it did and the overflow was silently clipped at the right edge
    ("Refresh Guid…") — the mechanism behind WIP-2. Reporting the content's
    width makes the editor's minimum honest; the content itself wraps.
    """

    def minimumSizeHint(self) -> QSize:  # noqa: N802 (Qt override)
        hint = super().minimumSizeHint()
        content = self.widget()
        if content is None:
            return hint
        frame = 2 * self.frameWidth()
        return QSize(max(hint.width(), content.minimumSizeHint().width() + frame), hint.height())


def _wrap_scroll(content: QWidget) -> QScrollArea:
    """Wrap *content* in a borderless, resizable vertical-scroll area — one
    shared helper so all three tabs scroll identically."""
    scroll = _VerticalScroll()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(content)
    return scroll


class _ProviderEditorTabsMixin:
    """Mixin: builds the Summary/Connection/Settings tab content."""

    # ── Tab assembly ─────────────────────────────────────────────────────── #

    def _build_summary_tab(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        self._build_header_row(layout)
        self._build_action_bar(layout)
        self._build_account_info_group(layout)
        layout.addStretch(1)
        return _wrap_scroll(content)

    def _build_connection_tab(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        # Shown only while adding a source (``_set_new_mode_chrome``). Says
        # what StreamSelect reads without the word "IPTV" (user report, Q1) and that the
        # link a provider usually sends works as-is.
        self._new_source_intro = QLabel(
            "StreamSelect plays Xtream accounts. Enter the server address, username "
            "and password your provider gave you, or paste the M3U link they "
            "sent and StreamSelect fills in all three. Name the source and pick its "
            "icon, colour or emoji on the Summary tab.")
        self._new_source_intro.setWordWrap(True)
        _theme.style(self._new_source_intro, "SECTION_HINT")
        self._new_source_intro.hide()
        layout.addWidget(self._new_source_intro)
        self._build_credentials_group(layout)
        self._build_urls_group(layout)
        # No trailing addStretch(1) here: the URLs group itself carries
        # stretch factor 1 (see _build_urls_group) so it fills the remaining
        # column height instead of capping at its content and leaving the
        # extra space blank below it.
        return _wrap_scroll(content)

    def _build_settings_tab(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        self._build_refresh_settings_group(layout)
        self._build_epg_group(layout)
        layout.addStretch(1)
        return _wrap_scroll(content)

    # ── Analytics (fourth tab) ──────────────────────────────────────────── #

    def _build_analytics_tab(self) -> QScrollArea:
        from streamselect.gui.source_analytics_tab import SourceAnalyticsTab

        self._analytics_tab = SourceAnalyticsTab(self._run_query_fn or self._run_query_inline)
        self._analytics_tab.browse_requested.connect(self.browse_ids_requested.emit)
        self._analytics_scroll = _wrap_scroll(self._analytics_tab)
        return self._analytics_scroll

    def _sync_analytics_tab(self) -> None:
        """Load the Analytics tab while it is the tab showing; drop its loads when not."""
        if self._tabs.currentWidget() is self._analytics_scroll:
            self._analytics_tab.show_provider(None if self._new_source else self._provider_id)
        else:
            self._analytics_tab.deactivate()

    def forget_analytics(self) -> None:
        """The catalogue changed: drop the cached title overlap, reload if showing."""
        self._analytics_tab.forget_cached_overlap()
        self._sync_analytics_tab()

    def _run_query_inline(self, query_fn, on_result, *, token_ref=None, on_error=None) -> None:
        """Synchronous stand-in for ``MainWindow._run_query`` when the editor is
        hosted without the seam (tests). The app always passes the real one."""
        try:
            with self.db.session_scope(commit=False) as session:
                result = query_fn(RepositoryFactory(session))
        except Exception as exc:  # surfaced on the section, like the seam's on_error
            if on_error is not None:
                on_error(exc)
            return
        on_result(result)

    # ── General settings (Settings tab) ─────────────────────────────────── #

    def _build_refresh_settings_group(self, layout: QVBoxLayout) -> None:
        group = QGroupBox("General")
        form = QFormLayout(group)
        form.setSpacing(8)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self._refresh_combo = QComboBox()
        self._refresh_combo.addItems(["Manual", "On App Launch", "Daily", "Weekly", "Every 30 Days"])
        self._refresh_combo.setToolTip(
            "How often StreamSelect automatically re-fetches this source's full "
            "catalog (channels, VOD, series, live event times) through the "
            "same refresh the button above runs. Sports/live-event data can "
            "go stale in hours; a movie library rarely needs more than a "
            "weekly refresh — pick what matches how you actually use this "
            "source. 'On App Launch' refreshes once, every time you open "
            "StreamSelect. A source currently streaming is skipped and retried "
            "once playback stops."
        )
        form.addRow("Auto-refresh:", self._refresh_combo)

        # Short: the row label already says "Adult content", and a checkbox's
        # text cannot wrap, so the long form set the editor's minimum width.
        self._force_adult_check = QCheckBox("Treat every channel as adult")
        self._force_adult_check.setToolTip(
            "Mark all channels from this source as adult content. Enable when "
            "this source doesn't tag channels with adult flags but you want the "
            "adult content filter to apply to it."
        )
        form.addRow("Adult content:", self._force_adult_check)

        layout.addWidget(group)
