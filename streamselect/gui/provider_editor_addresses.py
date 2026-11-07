"""Credentials and server addresses — the Connection tab of the Sources editor.

Mixed into :class:`~streamselect.gui.provider_editor.ProviderEditorView`. The
username/password fields, the address list (add, remove with undo, try-first)
and the address box, which also takes a provider's M3U link and fills in all
three parts (``core.xtream_link``).
"""
from __future__ import annotations


from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import (
    QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSizePolicy, QVBoxLayout,
)

from streamselect.core.models import ProviderURL
from streamselect.core.xtream_link import parse_xtream_link
from streamselect.gui import cursor_affordance
from streamselect.gui import icon_utils as _icon_utils
from streamselect.gui import theme as _theme
from streamselect.gui.url_row_widget import URLRowWidget


#: Why a source carries several addresses, and how the list is ordered (R3).
_ADDRESSES_HINT = (
    "Most providers give you several server addresses: add them all. StreamSelect "
    "tries the most reliable first and switches by itself when one is down or "
    "slow. ⤒ tries an address first next time; click an address to copy it.")


class _AddressesMixin:
    """Credentials and server addresses for the Sources editor. See the module docstring."""

    # ── Credentials (Connection tab) ────────────────────────────────────── #

    def _build_credentials_group(self, layout: QVBoxLayout) -> None:
        group = QGroupBox("Credentials")
        form = QFormLayout(group)
        form.setSpacing(8)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        un_row = QHBoxLayout()
        self._username_input = QLineEdit()
        self._username_input.setClearButtonEnabled(True)
        self._username_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._username_input.setPlaceholderText("username")
        un_row.addWidget(self._username_input, 1)
        self._username_eye_btn = QPushButton()
        _icon_utils.set_button_icon(self._username_eye_btn, "visibility_toggle")
        self._username_eye_btn.setToolTip("Show or hide the username")
        self._username_eye_btn.setFixedWidth(28)
        self._username_eye_btn.setCheckable(True)
        _theme.style(self._username_eye_btn, "EYE_BTN")
        self._username_eye_btn.toggled.connect(
            lambda checked: self._username_input.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        un_row.addWidget(self._username_eye_btn)
        form.addRow("Username:", un_row)

        pw_row = QHBoxLayout()
        self._password_input = QLineEdit()
        self._password_input.setClearButtonEnabled(True)
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.setPlaceholderText("password")
        pw_row.addWidget(self._password_input, 1)
        self._password_eye_btn = QPushButton()
        _icon_utils.set_button_icon(self._password_eye_btn, "visibility_toggle")
        self._password_eye_btn.setToolTip("Show or hide the password")
        self._password_eye_btn.setFixedWidth(28)
        self._password_eye_btn.setCheckable(True)
        _theme.style(self._password_eye_btn, "EYE_BTN")
        self._password_eye_btn.toggled.connect(
            lambda checked: self._password_input.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        pw_row.addWidget(self._password_eye_btn)
        form.addRow("Password:", pw_row)

        layout.addWidget(group)

    # ── DNS / URLs (Connection tab) ─────────────────────────────────────── #

    def _build_urls_group(self, layout: QVBoxLayout) -> None:
        # A group title neither wraps nor elides, so the sentence that used to
        # live in it set the whole editor's minimum width; it is a hint now.
        group = QGroupBox("Server addresses")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(6)
        hint = QLabel(_ADDRESSES_HINT)
        hint.setWordWrap(True)
        _theme.style(hint, "SECTION_HINT")
        group_layout.addWidget(hint)

        # Input ABOVE the list it feeds. A tester pasted URLs into the big
        # list below because that is the obvious target — the list is large and
        # looks like a text area, while the real input sat underneath it, out of
        # the reading path. Entry first, then the result of entering.
        add_row = QHBoxLayout()
        self._new_url_input = QLineEdit()
        self._new_url_input.setClearButtonEnabled(True)
        self._new_url_input.setPlaceholderText(
            "Server address (http://example.com:8080) or M3U link")
        self._new_url_input.setToolTip(
            "A server address, or the M3U link you were sent: its username "
            "and password are filled in for you. Add every address you were "
            "given; the extras take over when one is down.")
        self._new_url_input.returnPressed.connect(self._add_url)
        add_row.addWidget(self._new_url_input, 1)
        add_btn = QPushButton("Add URL")
        add_btn.setFixedWidth(80)
        add_btn.setToolTip("Add this address to the list below")
        cursor_affordance.set_clickable(add_btn)
        add_btn.clicked.connect(self._add_url)
        add_row.addWidget(add_btn)
        group_layout.addLayout(add_row)

        self._url_list = QListWidget()
        self._url_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._url_list.setSpacing(2)
        self._url_list.setToolTip(_ADDRESSES_HINT)
        # Vertical Expanding only — horizontal stays whatever QListWidget's
        # default already is. Paired with stretch factor 1 below (and on the
        # group itself) so the list fills the pane instead of capping at a
        # fixed ~4-row height.
        size_policy = self._url_list.sizePolicy()
        size_policy.setVerticalPolicy(QSizePolicy.Policy.Expanding)
        self._url_list.setSizePolicy(size_policy)
        group_layout.addWidget(self._url_list, 1)

        layout.addWidget(group, 1)

    def _rebuild_url_list(self) -> None:
        self._url_list.clear()
        total = len(self._provider_urls)
        for i, pu in enumerate(self._provider_urls):
            item = QListWidgetItem()
            pending = pu.url in self._pending_url_removals
            widget = URLRowWidget(pu, i, total, pending_remove=pending)
            # The last test's verdict outlives the reorder that follows it —
            # rebuilding the rows used to wipe every badge the moment the
            # test finished, so the per-address result was never readable.
            shown = self._url_test_results.get(pu.url.rstrip("/"))
            if shown:
                widget.show_test_result(*shown)
            widget.tryFirstToggled.connect(lambda pu=pu: self._on_try_first_toggled(pu))
            widget.removed.connect(lambda idx=i: self._remove_url(idx))
            widget.restored.connect(lambda url=pu.url: self._restore_url(url))
            item.setSizeHint(QSize(0, 58))
            self._url_list.addItem(item)
            self._url_list.setItemWidget(item, widget)

    def _add_url(self) -> None:
        url = self._new_url_input.text().strip()
        if not url:
            return
        # A provider's M3U link carries the server AND the login: take all
        # three, so the user can paste exactly what they were given.
        link = parse_xtream_link(url)
        if link:
            url = link.server
            self._username_input.setText(link.username)
            self._password_input.setText(link.password)
        if any(u.url.rstrip("/") == url.rstrip("/") for u in self._provider_urls):
            return  # duplicate
        max_pri = max((u.priority for u in self._provider_urls), default=-1)
        self._provider_urls.append(ProviderURL(url=url, priority=max_pri + 1))
        self._new_url_input.clear()
        # Caret back in the empty field: adding several fallback URLs in a row
        # is the normal case, and this surface already accepted Enter.
        self._new_url_input.setFocus()
        self._rebuild_url_list()
        self._invalidate_new_test()

    def _remove_url(self, idx: int) -> None:
        """Flip URL *idx* to pending-remove (ghost row + Undo) — Save is what
        actually deletes it. Keyed by url in ``_pending_url_removals``, never
        by index: indices shift as ghost rows accumulate. A new source has
        nothing saved to undo, so its rows just go.
        """
        if self._new_source:
            del self._provider_urls[idx]
            self._rebuild_url_list()
            self._invalidate_new_test()
            return
        pu = self._provider_urls[idx]
        surviving = sum(
            1 for p in self._provider_urls if p.url not in self._pending_url_removals
        )
        if pu.url not in self._pending_url_removals and surviving <= 1:
            QMessageBox.warning(self, "Cannot Remove", "At least one URL is required.")
            return
        self._pending_url_removals.add(pu.url)
        self._rebuild_url_list()

    def _restore_url(self, url: str) -> None:
        """Undo a pending removal — the row returns to normal."""
        self._pending_url_removals.discard(url)
        self._rebuild_url_list()

    def _on_try_first_toggled(self, pu: ProviderURL) -> None:
        """Flip one URL's one-shot try-first flag, then re-sort the display so
        an armed row leads. Python's sort is stable, so the existing
        (evidence-driven) order survives within each armed/unarmed group.
        """
        pu.try_first = not pu.try_first
        self._provider_urls.sort(key=lambda p: not p.try_first)
        self._rebuild_url_list()
