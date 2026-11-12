"""The Account Info group of the Sources editor (Summary tab).

Mixed into :class:`~streamselect.gui.provider_editor.ProviderEditorView`. Builds the
group, fetches the provider's account/subscription info, shows it, and saves
it onto the source.
"""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel,
    QProgressBar,
    QPushButton, QVBoxLayout, QWidget,
)
from loguru import logger

from streamselect.core.repositories import RepositoryFactory
from streamselect.core.repositories.provider import apply_account_info
from streamselect.core.time_display import date_text
from streamselect.gui import theme as _theme
from streamselect.gui.flow_layout import FlowLayout
from streamselect.gui.provider_editor_workers import FetchAccountInfoThread


class _AccountInfoMixin:
    """Account Info for the Sources editor. See the module docstring."""

    # ── Account Info (Summary tab) ──────────────────────────────────────── #

    def _build_account_info_group(self, layout: QVBoxLayout) -> None:
        group = QGroupBox("Account Info")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(8)

        # Status and dates rows: two "label value" pairs each, wrapping as
        # pairs when narrow rather than setting the editor's minimum width.
        self._acct_status_lbl = QLabel("—")
        _theme.style(self._acct_status_lbl, "FIELD_LABEL")
        self._acct_cons_lbl = QLabel("—")
        _theme.style(self._acct_cons_lbl, "FIELD_LABEL")
        self._acct_created_lbl = QLabel("—")
        self._acct_exp_lbl = QLabel("—")
        for pairs in ((("Status:", self._acct_status_lbl), ("Connections:", self._acct_cons_lbl)),
                      (("Created:", self._acct_created_lbl), ("Expires:", self._acct_exp_lbl))):
            row = QWidget()
            flow = FlowLayout(row, h_spacing=24, v_spacing=8)
            flow.setContentsMargins(0, 0, 0, 0)
            for caption, value in pairs:
                pair = QWidget()
                pl = QHBoxLayout(pair)
                pl.setContentsMargins(0, 0, 0, 0)
                pl.addWidget(QLabel(caption))
                pl.addWidget(value)
                flow.addWidget(pair)
            group_layout.addWidget(row)

        # EPG guide status — surfaces a provider feed serving stale/out-of-date data
        # (so a blank EPG view reads as "provider's guide is stale", not "our bug").
        # Mirrored by _epg_freshness_lbl in the Settings tab's EPG group — both are
        # kept in sync by _set_epg_status_label (single source of truth).
        epg_row = QHBoxLayout()
        epg_row.addWidget(QLabel("EPG guide:"), 0, Qt.AlignmentFlag.AlignTop)
        self._acct_epg_lbl = QLabel("—")
        self._acct_epg_lbl.setWordWrap(True)   # the freshness line runs long
        epg_row.addWidget(self._acct_epg_lbl, 1)
        group_layout.addLayout(epg_row)

        # Remaining: the words, then the bar on its own line — side by side
        # they set the editor's minimum width.
        bar_row = QHBoxLayout()
        bar_row.addWidget(QLabel("Remaining:"))
        self._acct_remaining_lbl = QLabel("—")
        bar_row.addWidget(self._acct_remaining_lbl, 1)
        group_layout.addLayout(bar_row)
        self._acct_progress = QProgressBar()
        self._acct_progress.setTextVisible(False)
        self._acct_progress.setRange(0, 100)
        self._acct_progress.setValue(0)
        self._acct_progress.hide()
        group_layout.addWidget(self._acct_progress)

        # Refresh button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._refresh_acct_btn = QPushButton("↻  Refresh Account Info")
        self._refresh_acct_btn.setToolTip("Ask the source again for its expiry date and connection limit")
        self._refresh_acct_btn.clicked.connect(self._fetch_account_info)
        btn_row.addWidget(self._refresh_acct_btn)
        group_layout.addLayout(btn_row)

        self._acct_error_lbl = QLabel("")
        _theme.style_fn(self._acct_error_lbl, lambda: f"color: {_theme.COLOR_ERR_2}; font-size: {_theme.FONT_MD};")
        self._acct_error_lbl.hide()
        group_layout.addWidget(self._acct_error_lbl)

        layout.addWidget(group)

    def _fetch_account_info(self) -> None:

        if self._new_source and self._provider_urls:
            self._account_thread = FetchAccountInfoThread(self._draft_provider())
            self._account_thread.finished.connect(self._on_account_info_fetched)
            self._account_thread.start()
            return
        if not self._provider_id:
            return
        self._refresh_acct_btn.setEnabled(False)
        self._refresh_acct_btn.setText("Fetching…")
        self._acct_error_lbl.hide()

        session = self.db.get_session()
        try:
            repos = RepositoryFactory(session)
            db_prov = repos.providers.get_by_id(self._provider_id)
            if not db_prov:
                return
            provider = repos.providers.to_model(db_prov)
        finally:
            session.close()

        self._account_thread = FetchAccountInfoThread(provider)
        self._account_thread.finished.connect(self._on_account_info_fetched)
        self._account_thread.start()

    def _on_account_info_fetched(self, success: bool, result) -> None:
        self._refresh_acct_btn.setEnabled(True)
        self._refresh_acct_btn.setText("↻  Refresh Account Info")

        if not success:
            self._acct_error_lbl.setText(f"Failed: {result}")
            self._acct_error_lbl.show()
            return

        info = result
        self._pending_account_info = info  # stored on save

        # Parse timestamps
        exp_dt = self._parse_ts(info.get("exp_date"))
        created_dt = self._parse_ts(info.get("created_at"))

        self._apply_account_info({
            "status": info.get("status", ""),
            "exp_date_dt": exp_dt,
            "created_at_dt": created_dt,
            "active_cons": info.get("active_cons", 0),
            "max_connections": info.get("max_connections", 1),
        })

        # Account fetch never changes is_active — only the expiry-derived half of
        # the name-row status dot can have moved.
        self._current_is_expired = bool(exp_dt and exp_dt <= datetime.now())
        self._update_status_dot(self._current_is_active, self._current_is_expired)

        # Auto-save fresh account info to database immediately
        self._persist_account_info(info)

    def _apply_account_info(self, data: dict, from_cache: bool = False) -> None:
        """Populate account info labels from a data dict."""
        status = data.get("status", "")
        exp_dt = data.get("exp_date_dt")
        created_dt = data.get("created_at_dt")
        active_cons = data.get("active_cons", 0)
        max_cons = data.get("max_connections", 1)

        # Status label
        if status.lower() == "active":
            color = _theme.COLOR_OK
        elif status.lower() == "expired":
            color = _theme.COLOR_ERR
        elif status:
            color = _theme.COLOR_WARN
        else:
            color = _theme.COLOR_MUTED
        self._acct_status_lbl.setText(status or "Unknown")
        self._acct_status_lbl.setStyleSheet(f"font-weight: 600; color: {color};")

        # Connections
        self._acct_cons_lbl.setText(f"{active_cons} / {max_cons}")

        # Dates
        self._acct_created_lbl.setText(date_text(created_dt) if created_dt else "—")
        self._acct_exp_lbl.setText(date_text(exp_dt) if exp_dt else "—")

        # Remaining bar
        if exp_dt:
            from streamselect.gui.subscription_status import subscription_color
            now = datetime.now()
            col = subscription_color(exp_dt, created_dt)
            if exp_dt > now:
                days_left = (exp_dt - now).days
                total_days = (exp_dt - created_dt).days if created_dt else 30
                pct = max(0, min(100, int(days_left / total_days * 100))) if total_days > 0 else 100
                suffix = " (cached)" if from_cache else ""
                self._acct_remaining_lbl.setText(f"{days_left} days  ({pct}%){suffix}")
                self._acct_remaining_lbl.setStyleSheet(f"font-weight: 600; color: {col};")
                self._acct_progress.setValue(pct)
                # The subscription hue — green/amber/red by how long is left.
                _theme.style_fn(self._acct_progress,
                                lambda c=col: _theme.progress_bar(c))
                self._acct_progress.show()
            else:
                self._acct_remaining_lbl.setText("Expired")
                _theme.style_fn(self._acct_remaining_lbl, lambda: f"font-weight: 600; color: {_theme.COLOR_ERR};")
                self._acct_progress.setValue(0)
                self._acct_progress.show()
        else:
            self._acct_remaining_lbl.setText("—")
            self._acct_progress.hide()

    def _persist_account_info(self, info: dict) -> None:
        """Immediately save fresh account info to database.

        Called when account refresh succeeds, so changes persist even if user
        navigates away without clicking Save. Emits account_info_updated signal
        so sidebar can refresh its display.
        """
        from streamselect.core.database import ProviderDB

        if not self._provider_id or not info:
            return

        session = self.db.get_session()
        try:
            db_prov = session.query(ProviderDB).filter_by(id=self._provider_id).first()
            if not db_prov:
                return

            apply_account_info(db_prov, info)
            db_prov.updated_at = datetime.now()
            session.commit()
            logger.info(f"Account info auto-saved for '{db_prov.name}'")
            self.account_info_updated.emit(self._provider_id)
        except Exception as e:
            logger.error(f"Failed to auto-save account info: {e}")
        finally:
            session.close()
