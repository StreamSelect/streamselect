"""Settings → Metadata & API Keys: enrichment, the TMDb/OMDb keys (with their off-thread
"Test" buttons) and the EPG guide timings.

Its own module because ``settings_dialog_tabs.py`` sat at its code-health ceiling and
the Settings rework needed room there (2026-11-22). Mixed into ``SettingsDialog``, so the
widgets are the dialog's own attributes, read and written by ``_load_values``/``_save_values``.
"""
from __future__ import annotations

import asyncio
import html as _html
from types import SimpleNamespace

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from streamselect.core.epg_utils import EPG_INTERVAL_CHOICES, EPG_SCRUBBER_INCREMENTS
from streamselect.gui import icon_utils as _icon_utils
from streamselect.gui import theme as _theme


class SettingsMetadataTabMixin:
    """The Metadata & API Keys page and its TMDb/OMDb key tests."""

    def _build_metadata_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)
        layout.setContentsMargins(12, 12, 12, 12)

        meta_group = QGroupBox("Metadata Enrichment")
        meta_form = QFormLayout(meta_group)
        meta_form.setSpacing(8)

        self._meta_enabled_check = QCheckBox("Enable metadata enrichment")
        self._meta_enabled_check.setToolTip("Look titles up on the internet for posters, plots, cast "
            "and ratings. Off: only what your sources send is shown.")
        meta_form.addRow(self._meta_enabled_check)

        self._meta_autofetch_check = QCheckBox("Auto-fetch on channel select")
        self._meta_autofetch_check.setToolTip("Look a title up as soon as you select it. Off: details "
            "come only from the background lookup or when you refresh a title by hand.")
        meta_form.addRow(self._meta_autofetch_check)

        self._cache_ttl_spin = QSpinBox()
        self._cache_ttl_spin.setRange(1, 365)
        self._cache_ttl_spin.setSuffix(" days")
        meta_form.addRow("Cache TTL (fresh content):", self._cache_ttl_spin)

        self._cache_old_ttl_spin = QSpinBox()
        self._cache_old_ttl_spin.setRange(1, 365)
        self._cache_old_ttl_spin.setSuffix(" days")
        self._cache_old_ttl_spin.setToolTip("The background lookup fetches a title's details again "
            "once the stored ones are this old.")
        meta_form.addRow("Cache TTL (old content >2yr):", self._cache_old_ttl_spin)

        layout.addWidget(meta_group)

        tmdb_group = QGroupBox("TMDb")
        tmdb_form = QFormLayout(tmdb_group)
        tmdb_form.setSpacing(8)

        tmdb_key_row = QHBoxLayout()
        self._tmdb_key_input = QLineEdit()
        self._tmdb_key_input.setClearButtonEnabled(True)
        self._tmdb_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._tmdb_key_input.setPlaceholderText("your-tmdb-api-key")
        self._tmdb_key_input.setToolTip("Your free TMDb key. It unlocks posters, plots, cast and "
            "similar titles. Get key opens the page that issues one; Test checks it.")
        tmdb_key_row.addWidget(self._tmdb_key_input, 1)
        tmdb_link_btn = QPushButton("Get key →")
        tmdb_link_btn.setFixedWidth(80)
        _theme.style_fn(tmdb_link_btn, lambda: f"QPushButton {{ color: {_theme.COLOR_ACCENT_BLUE}; border: none; padding: 0; }}"
            f" QPushButton:hover {{ color: {_theme.COLOR_ACCENT_BLUE_2}; }}")
        tmdb_link_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://www.themoviedb.org/settings/api"))
        )
        tmdb_key_row.addWidget(tmdb_link_btn)
        self._tmdb_test_btn = QPushButton("Test")
        self._tmdb_test_btn.setFixedWidth(50)
        self._tmdb_test_btn.setEnabled(self._executor is not None)
        self._tmdb_test_btn.setToolTip(
            "Test this TMDb API key" if self._executor is not None
            else "Test unavailable — no background executor for this dialog instance"
        )
        self._tmdb_test_btn.clicked.connect(self._on_test_tmdb_key)
        tmdb_key_row.addWidget(self._tmdb_test_btn)
        tmdb_form.addRow("API key:", tmdb_key_row)

        self._tmdb_test_result = QLabel("")
        _theme.style(self._tmdb_test_result, "URL_BADGE")
        self._tmdb_test_result.hide()
        tmdb_form.addRow(self._tmdb_test_result)

        self._tmdb_lang_input = QLineEdit()
        self._tmdb_lang_input.setClearButtonEnabled(True)
        self._tmdb_lang_input.setPlaceholderText("en-US")
        self._tmdb_lang_input.setMaxLength(10)
        self._tmdb_lang_input.setToolTip("The language TMDb answers in, as a code such as en-US, "
            "fr-FR or es-MX. Titles and plots come back in it where TMDb has a translation.")
        tmdb_form.addRow("Language:", self._tmdb_lang_input)

        layout.addWidget(tmdb_group)

        omdb_group = QGroupBox("OMDb")
        omdb_form = QFormLayout(omdb_group)
        omdb_form.setSpacing(8)

        omdb_key_row = QHBoxLayout()
        self._omdb_key_input = QLineEdit()
        self._omdb_key_input.setClearButtonEnabled(True)
        self._omdb_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._omdb_key_input.setPlaceholderText("your-omdb-api-key")
        self._omdb_key_input.setToolTip("Your free OMDb key. It adds IMDb and Rotten Tomatoes "
            "ratings. Get key opens the page that issues one; Test checks it.")
        omdb_key_row.addWidget(self._omdb_key_input, 1)
        omdb_link_btn = QPushButton("Get key →")
        omdb_link_btn.setFixedWidth(80)
        _theme.style_fn(omdb_link_btn, lambda: f"QPushButton {{ color: {_theme.COLOR_ACCENT_BLUE}; border: none; padding: 0; }}"
            f" QPushButton:hover {{ color: {_theme.COLOR_ACCENT_BLUE_2}; }}")
        omdb_link_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://www.omdbapi.com/apikey.aspx"))
        )
        omdb_key_row.addWidget(omdb_link_btn)
        self._omdb_test_btn = QPushButton("Test")
        self._omdb_test_btn.setFixedWidth(50)
        self._omdb_test_btn.setEnabled(self._executor is not None)
        self._omdb_test_btn.setToolTip(
            "Test this OMDb API key" if self._executor is not None
            else "Test unavailable — no background executor for this dialog instance"
        )
        self._omdb_test_btn.clicked.connect(self._on_test_omdb_key)
        omdb_key_row.addWidget(self._omdb_test_btn)
        omdb_form.addRow("API key:", omdb_key_row)

        self._omdb_test_result = QLabel("")
        _theme.style(self._omdb_test_result, "URL_BADGE")
        self._omdb_test_result.hide()
        omdb_form.addRow(self._omdb_test_result)

        layout.addWidget(omdb_group)

        epg_group = QGroupBox("EPG")
        epg_form = QFormLayout(epg_group)
        epg_form.setSpacing(8)

        self._epg_interval_combo = QComboBox()
        for value, label in EPG_INTERVAL_CHOICES:
            self._epg_interval_combo.addItem(label, value)
        self._epg_interval_combo.setToolTip(
            "Default EPG guide refresh frequency for all providers. "
            "Individual providers can override this in their editor. "
            "'Auto' (the default) self-tunes: it refreshes at half the guide depth, "
            "clamped to 6 hours – 7 days, so there is always headroom. "
            "'Only when data is stale' waits until the guide has fully expired before re-fetching."
        )
        epg_form.addRow("EPG refresh:", self._epg_interval_combo)

        self._epg_hide_older_spin = QSpinBox()
        self._epg_hide_older_spin.setRange(0, 168)  # 0 = no extra back-browse … 7 days
        self._epg_hide_older_spin.setSuffix(" h")
        self._epg_hide_older_spin.setToolTip(
            "Browse opens at 'now' (currently-airing + upcoming) and its timeline\n"
            "reaches back to the start of everything on right now. This setting lets\n"
            "you scrub FURTHER back: drag the handle to browse up to this many hours\n"
            "into the past. 0 (the default) keeps the timeline at the oldest show\n"
            "currently airing — no further back."
        )
        epg_form.addRow("Allow browsing back:", self._epg_hide_older_spin)

        self._epg_scrubber_increment_combo = QComboBox()
        for _mins in EPG_SCRUBBER_INCREMENTS:
            self._epg_scrubber_increment_combo.addItem(f"{_mins} minutes", _mins)
        self._epg_scrubber_increment_combo.setToolTip(
            "Granularity of the Browse timeline scrubber. Dragging the handle snaps to "
            "this interval (and each scroll step of the handle is one interval)."
        )
        epg_form.addRow("Scrubber snap:", self._epg_scrubber_increment_combo)

        self._epg_notify_minutes_spin = QSpinBox()
        self._epg_notify_minutes_spin.setRange(5, 120)
        self._epg_notify_minutes_spin.setSuffix(" min")
        self._epg_notify_minutes_spin.setToolTip(
            "How many minutes before a Watchlist programme starts StreamSelect shows a "
            "notification toast."
        )
        epg_form.addRow("Notify before show:", self._epg_notify_minutes_spin)
        self._epg_runout_spin = QSpinBox(minimum=10, maximum=360, suffix=" min")
        self._epg_runout_spin.setToolTip("Fetch a new guide this long before its last listed "
                                         "programme starts, so the guide never runs out first.")
        epg_form.addRow("Refresh before it runs out:", self._epg_runout_spin)

        self._epg_auto_refresh_check = QCheckBox("Auto-refresh guides on launch and interval")
        self._epg_auto_refresh_check.setToolTip(
            "When on, StreamSelect automatically fetches new EPG guide data on launch and "
            "at each source's refresh interval. Turn off to only refresh EPG "
            "manually (the Refresh button on the EPG screen still works)."
        )
        epg_form.addRow(self._epg_auto_refresh_check)

        layout.addWidget(epg_group)

        layout.addStretch()
        return tab

    # ── TMDb/OMDb "Test" buttons ────────────────────────────────────────────
    # Off-UI-thread: the worker only emits `_provider_test_ready`; its slot alone
    # touches the result badges. Tests the key CURRENTLY TYPED (test before save).

    def _on_test_tmdb_key(self) -> None:
        """Metadata tab: TMDb 'Test' button clicked."""
        from streamselect.metadata_providers.tmdb import TMDbProvider
        key = self._tmdb_key_input.text().strip()
        language = self._tmdb_lang_input.text().strip() or "en-US"
        provider = TMDbProvider(SimpleNamespace(
            metadata_tmdb_api_key=key,
            metadata_tmdb_language=language,
            metadata_tmdb_include_adult=False,
        ))
        self._run_provider_test("tmdb", provider, self._tmdb_test_btn, self._tmdb_test_result)

    def _on_test_omdb_key(self) -> None:
        """Metadata tab: OMDb 'Test' button clicked."""
        from streamselect.metadata_providers.omdb import OMDbProvider
        key = self._omdb_key_input.text().strip()
        provider = OMDbProvider(SimpleNamespace(metadata_omdb_api_key=key))
        self._run_provider_test("omdb", provider, self._omdb_test_btn, self._omdb_test_result)

    def _run_provider_test(self, provider_name: str, provider, button: QPushButton,
                            label: QLabel) -> None:
        """Kick off ``provider.test_connection()`` on the shared executor.

        Args:
            provider_name: ``"tmdb"``/``"omdb"`` — echoed back by the worker so
                ``_on_provider_test_ready`` knows which widgets to update.
            provider: A throwaway provider built from the typed (unsaved) key.
            button: The "Test" button to disable while the probe is in flight.
            label: The inline result-badge label to update.
        """
        if self._executor is None:
            label.setText(f"{_icon_utils.role_html('notification_error')}&nbsp;Test unavailable — no executor")
            _theme.style(label, "URL_BADGE_ERR")
            label.show()
            return
        if not provider.is_enabled():
            label.setText(f"{_icon_utils.role_html('notification_error')}&nbsp;Enter an API key first")
            _theme.style(label, "URL_BADGE_ERR")
            label.show()
            return
        button.setEnabled(False)
        label.setText(f"{_icon_utils.role_html('loading')}&nbsp;Testing…")
        _theme.style(label, "URL_BADGE_TESTING")
        label.show()
        self._executor.submit(self._provider_test_worker, provider_name, provider)

    def _provider_test_worker(self, provider_name: str, provider) -> None:
        """Runs OFF the main thread. Never touches widgets — emits the result only.

        Args:
            provider_name: ``"tmdb"`` or ``"omdb"``.
            provider: The provider instance to probe.
        """
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(provider.test_connection())
            finally:
                loop.close()
        except Exception as e:  # pragma: no cover - defensive; must never escape a worker thread
            result = (False, f"Unexpected error: {e}")
        self._provider_test_ready.emit(provider_name, result)

    def _on_provider_test_ready(self, provider_name: str, result) -> None:
        """MAIN THREAD ONLY: render a Test-button result (success/failure + icon).

        Args:
            provider_name: ``"tmdb"`` or ``"omdb"``.
            result: ``(success, message)`` from ``test_connection()``.
        """
        if provider_name == "tmdb":
            button, label = self._tmdb_test_btn, self._tmdb_test_result
        elif provider_name == "omdb":
            button, label = self._omdb_test_btn, self._omdb_test_result
        else:
            return
        button.setEnabled(self._executor is not None)

        success, message = result
        if success:
            label.setText(f"{_icon_utils.role_html('notification_success')}&nbsp;Connected")
            _theme.style(label, "URL_BADGE_OK")
        else:
            label.setText(f"{_icon_utils.role_html('notification_error')}&nbsp;{_html.escape(message or 'Test failed', quote=False)}")
            _theme.style(label, "URL_BADGE_ERR")
        label.show()
