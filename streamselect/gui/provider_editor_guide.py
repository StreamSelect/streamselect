"""The EPG (guide) group of the Sources editor (Settings tab).

Mixed into :class:`~streamselect.gui.provider_editor.ProviderEditorView`. The guide
switch, URL override, refresh interval, the autodetected guide URL and the
freshness line, whose look per state is chosen here once.
"""
from __future__ import annotations

import html as _html

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QLabel,
    QLineEdit, QVBoxLayout, QWidget,
)

from streamselect.gui import icon_utils as _icon_utils
from streamselect.gui import theme as _theme
from streamselect.gui.flow_layout import FlowLayout


#: Guide-freshness state -> (glyph, colour token name). The state and its words
#: are decided once in ``epg_utils.guide_freshness``; this is the only place the
#: LOOK of each state is chosen, so the two labels that share the computation
#: also share the rendering. Colour never travels alone — every state that is
#: not "current" is announced by its own glyph as well.
_EPG_FRESHNESS_LOOK: dict[str, tuple[str, str]] = {
    "not_configured":  ("",                              "COLOR_TEXT"),
    "no_data":         ("",                              "COLOR_TEXT"),
    "current":         ("",                              "COLOR_OK"),
    "source_lagging":  ("warning",            "COLOR_WARN"),
    "fetch_failed":    ("notification_error", "COLOR_ERR"),
    "override_failed": ("notification_error", "COLOR_ERR"),
}

#: Tooltip for the states that have nothing more to say than the line already does.
_EPG_FRESHNESS_DEFAULT_TIP = (
    "Current state of the downloaded EPG guide data for this source."
)


class _GuideSettingsMixin:
    """The EPG group for the Sources editor. See the module docstring."""

    # ── EPG (Settings tab) ───────────────────────────────────────────────── #

    def _build_epg_group(self, layout: QVBoxLayout) -> None:
        """Build the EPG configuration group box with all EPG controls.

        The manual "refresh now" trigger for this group lives in the Summary
        tab's action bar (``ProviderEditorView._build_action_bar`` →
        ``self._epg_refresh_btn``, reused from its pre-Wave-7 location so this
        group only owns enable / URL override / refresh-interval / freshness —
        the group's job is configuration, not the one-off action.
        """
        from streamselect.core.epg_utils import EPG_INTERVAL_CHOICES
        from streamselect.gui.url_row_widget import _ClickToCopyLabel

        group = QGroupBox("TV guide (EPG)")
        outer = QVBoxLayout(group)
        outer.setSpacing(8)

        explainer = QLabel(
            "A TV guide lists what is playing on each live channel and when. "
            "With it you get the EPG view, On Now, and the ability to set "
            "reminders for upcoming programmes. Most sources publish one "
            "automatically. Leave this on unless the guide is wrong or you "
            "want to save the download."
        )
        explainer.setWordWrap(True)
        _theme.style(explainer, "SECTION_HINT")
        outer.addWidget(explainer)

        form_host = QWidget()
        form = QFormLayout(form_host)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        outer.addWidget(form_host)

        # 1. Enable / disable — with a right-aligned auto-detect status badge
        self._epg_enabled_check = QCheckBox("Fetch EPG guide for this source")
        self._epg_enabled_check.setChecked(True)
        self._epg_enabled_check.setToolTip(
            "When enabled, StreamSelect downloads this source's XMLTV guide data and "
            "shows programme info in the EPG view, On Now, and Watchlist. "
            "Disabling immediately removes the fetched guide data for this source "
            "and skips it on future EPG refreshes. Re-enabling allows the next "
            "refresh to re-fetch it."
        )
        self._epg_detect_badge = QLabel("")
        self._epg_detect_badge.setTextFormat(Qt.TextFormat.RichText)
        # The badge follows the checkbox and wraps under it when narrow.
        enable_container = QWidget()
        enable_row = FlowLayout(enable_container, spacing=12)
        enable_row.setContentsMargins(0, 0, 0, 0)
        enable_row.addWidget(self._epg_enabled_check)
        enable_row.addWidget(self._epg_detect_badge)
        form.addRow("Enable EPG:", enable_container)

        # 1b. Auto-detected URL (smaller, click-to-copy). Hidden when none detected.
        self._epg_autodetected_lbl = _ClickToCopyLabel()
        _theme.style_fn(self._epg_autodetected_lbl,
                        lambda: f"font-size: {_theme.FONT_SM}; color: {_theme.COLOR_TEXT};")
        self._epg_autodetected_lbl.setVisible(False)
        form.addRow("", self._epg_autodetected_lbl)

        # 2. URL override
        self._epg_url_override_input = QLineEdit()
        self._epg_url_override_input.setClearButtonEnabled(True)
        self._epg_url_override_input.setPlaceholderText("(uses auto-detected URL)")
        self._epg_url_override_input.setToolTip(
            "Optional: supply your own XMLTV URL for this source. "
            "Leave blank to use the auto-detected feed. "
            "Changing this URL forces the guide to re-fetch on next refresh."
        )
        form.addRow("XMLTV URL override:", self._epg_url_override_input)

        # 3. Freshness label (read-only) — mirrors Account Info's "EPG guide:" line
        # (self._acct_epg_lbl); both are kept in sync by _set_epg_status_label.
        self._epg_freshness_lbl = QLabel("—")
        self._epg_freshness_lbl.setWordWrap(True)
        self._epg_freshness_lbl.setToolTip(
            "Current state of the downloaded EPG guide data for this source."
        )
        form.addRow("Guide freshness:", self._epg_freshness_lbl)

        # 4. Refresh interval
        self._epg_interval_combo = QComboBox()
        self._epg_interval_combo.addItem("Use default (from Settings)", "default")
        for value, label in EPG_INTERVAL_CHOICES:
            self._epg_interval_combo.addItem(label, value)
        self._epg_interval_combo.setToolTip(
            "How often to re-fetch this source's EPG guide. "
            "'Use default' inherits the global setting from Settings → EPG refresh "
            "(the default is Auto). "
            "'Auto' self-tunes: it refreshes at half the guide's depth, clamped to "
            "6 hours – 7 days, so there is always guide headroom. "
            "'Only when data is stale' waits until the guide has fully expired."
        )
        form.addRow("Refresh interval:", self._epg_interval_combo)

        # Disable EPG controls when the checkbox is unchecked
        self._epg_enabled_check.toggled.connect(self._update_epg_controls_enabled)
        self._epg_url_override_input.textChanged.connect(
            lambda _: self._update_epg_refresh_btn_state()
        )
        self._update_epg_controls_enabled(self._epg_enabled_check.isChecked())

        layout.addWidget(group)

    def _update_epg_controls_enabled(self, enabled: bool) -> None:
        """Enable/disable EPG sub-controls based on the Enable EPG checkbox."""
        self._epg_url_override_input.setEnabled(enabled)
        self._epg_interval_combo.setEnabled(enabled)
        self._update_epg_refresh_btn_state()

    def _update_epg_refresh_btn_state(self) -> None:
        """Enable the action bar's "Refresh Guide" button when EPG is on and an
        effective URL exists — the override OR the auto-detected URL (so the
        built-in feed can be refreshed without typing a custom URL)."""
        enabled = self._epg_enabled_check.isChecked()
        has_url = bool(
            self._epg_url_override_input.text().strip()
            or (self._provider_id and getattr(self, "_loaded_epg_url", ""))
        )
        self._epg_refresh_btn.setEnabled(enabled and has_url)

    def _update_epg_autodetected_display(self) -> None:
        """Render the right-aligned auto-detect badge and the click-to-copy auto URL
        line from ``self._loaded_epg_url``: green AUTODETECTED + the URL when one
        exists, red NOT FOUND with the URL line hidden otherwise."""
        auto_url = getattr(self, "_loaded_epg_url", "") or ""
        if auto_url:
            self._epg_detect_badge.setText(
                f"{_icon_utils.role_html('status_dot', color=_theme.COLOR_OK)} AUTODETECTED"
            )
            self._epg_detect_badge.setToolTip(
                "An XMLTV guide URL was auto-detected from this source's credentials."
            )
            self._epg_autodetected_lbl.set_url(auto_url)
            self._epg_autodetected_lbl.setVisible(True)
        else:
            self._epg_detect_badge.setText(
                f"{_icon_utils.role_html('status_dot', color=_theme.COLOR_ERR)} NOT FOUND"
            )
            self._epg_detect_badge.setToolTip(
                "No XMLTV guide URL could be auto-detected. Add a URL override to fetch EPG."
            )
            self._epg_autodetected_lbl.set_url("")
            self._epg_autodetected_lbl.setVisible(False)

    def _set_epg_status_label(
        self, epg_url, epg_data_end, epg_data_start=None, *,
        last_fetch_error=None, last_fetch_error_at=None, has_url_override=False,
    ) -> None:
        """Populate both EPG-guide status lines (Account Info's "EPG guide:" and
        Settings' "Guide freshness:" — one computation, two displays) from the
        provider's cached EPG fields.

        The words and the state come from ``epg_utils.guide_freshness`` (core, so
        it can be tested without Qt and cannot word the same state two ways);
        this method only renders them — glyph from ``icons.py``, colour from a
        token, and the full cause in the tooltip. Colour is never alone: every
        state that is not "current" carries its own glyph.

        Args:
            epg_url:             Effective EPG URL (auto-detected or override).
            epg_data_end:        Latest non-filler programme stop (UTC-naive).
            epg_data_start:      Earliest programme start (UTC-naive); used only
                                 for the Auto depth annotation.
            last_fetch_error:    ``ProviderDB.epg_last_fetch_error`` — the
                                 condensed cause of the last FAILED fetch.
            last_fetch_error_at: When that failure happened (UTC-naive).
            has_url_override:    Whether the user supplied their own EPG URL —
                                 what separates "your override is broken" from
                                 "every host we tried failed".
        """
        from streamselect.core.epg_utils import guide_freshness

        fresh = guide_freshness(
            epg_url, epg_data_end,
            epg_data_start=epg_data_start,
            last_fetch_error=last_fetch_error,
            last_fetch_error_at=last_fetch_error_at,
            has_url_override=has_url_override,
        )
        role, colour_token = _EPG_FRESHNESS_LOOK[fresh.state]
        text = (f"{_icon_utils.role_html(role)}&nbsp;{_html.escape(fresh.text, quote=False)}"
                if role else fresh.text)
        tooltip = fresh.detail or _EPG_FRESHNESS_DEFAULT_TIP

        for lbl in (self._acct_epg_lbl, self._epg_freshness_lbl):
            lbl.setText(text)
            lbl.setToolTip(tooltip)
            _theme.style_fn(lbl, lambda t=colour_token: f"color: {getattr(_theme, t)};")
