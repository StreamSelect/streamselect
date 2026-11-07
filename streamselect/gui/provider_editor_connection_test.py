"""Test Connection in the Sources editor, from the click to the explanation.

Mixed into :class:`~streamselect.gui.provider_editor.ProviderEditorView`. One job end
to end: probe every address at once, show each row's result as it arrives,
explain a total failure in the diagnosis panel, then reorder the addresses
fastest-first and fetch the account info if one worked. It remembers which
addresses answered as an Xtream server while the source is open, so a later
refusal reads as a lock-out rather than a wrong address.
"""
from __future__ import annotations

from typing import List


from streamselect.core.models import ProviderURL
from streamselect.gui import icon_utils as _icon_utils
from streamselect.gui.connection_diagnosis_text import _DIAGNOSIS_TEXT
from streamselect.gui.provider_editor_workers import TestAllURLsThread


class _ConnectionTestMixin:
    """Test Connection for the Sources editor. See the module docstring."""

    def _test_connection(self):
        """Test ALL configured URLs in parallel, then reorder by response time."""
        if self._new_source:
            self._take_typed_url()
        if not (self._provider_id or self._new_source) or not self._provider_urls:
            return

        username = self._username_input.text().strip()
        password = self._password_input.text().strip()
        urls = [pu.url for pu in self._provider_urls]

        self._test_btn.setEnabled(False)
        self._test_btn.setText(f"Testing 0/{len(urls)}…")
        self._acct_error_lbl.hide()
        self._test_results_pending = len(urls)
        self._url_test_results = {}

        # Show "Testing…" badge on every row
        from streamselect.gui.url_row_widget import URLRowWidget
        for i in range(self._url_list.count()):
            w = self._url_list.itemWidget(self._url_list.item(i))
            if isinstance(w, URLRowWidget):
                w.show_testing()

        # An address that has answered as an Xtream server before — a past
        # success, or an earlier test here, even one that rejected the
        # password — is the right address; a refusal from it now is a block.
        answered = frozenset(
            self._answered_urls
            | {pu.url for pu in self._provider_urls if pu.success_count or pu.last_success})
        self._test_thread = TestAllURLsThread(urls, username, password, answered)
        self._test_thread.url_result.connect(self._on_single_url_result)
        self._test_thread.all_done.connect(self._on_all_urls_done)
        self._test_thread.diagnosis.connect(self._on_diagnosis)
        self._test_thread.start()

    def _on_single_url_result(self, url: str, success: bool, ms: int, message: str):
        """Update the matching URL row badge as each result arrives."""
        from streamselect.gui.url_row_widget import URLRowWidget
        self._test_results_pending = max(0, self._test_results_pending - 1)
        total = len(self._provider_urls)
        done = total - self._test_results_pending
        self._test_btn.setText(f"Testing {done}/{total}…")

        self._url_test_results[url.rstrip("/")] = (success, message)
        for i in range(self._url_list.count()):
            w = self._url_list.itemWidget(self._url_list.item(i))
            if isinstance(w, URLRowWidget) and w.provider_url.url == url:
                w.show_test_result(success, message)
                break

    def _on_diagnosis(self, report) -> None:
        """Show why every address failed — or hide the panel when one worked.

        Only speaks up on a TOTAL failure. A partial failure is normal and is
        the entire reason a source carries several addresses; announcing it
        would train the user to ignore this panel.
        """
        self._answered_urls.update(report.answered)
        phrasing = _DIAGNOSIS_TEXT.get(report.diagnosis)
        if phrasing is None:
            self._diagnosis_lbl.hide()
            return

        headline, advice = phrasing
        evidence = ""
        if report.refusal_codes:
            evidence = f" (HTTP {', '.join(report.refusal_codes)})"
        self._diagnosis_lbl.setText(
            f"{headline}{evidence}\n\n{advice}"
        )
        self._diagnosis_lbl.show()

    def _on_all_urls_done(self, sorted_results: list):
        """Reorder URL list: successes fastest-first, failures last."""
        self._test_btn.setEnabled(True)
        working = [r for r in sorted_results if r[1]]
        failed  = [r for r in sorted_results if not r[1]]

        _icon_utils.set_button_icon(self._test_btn, "notification_success" if working else "notification_error")
        self._test_btn.setText(
            f"{len(working)}/{len(sorted_results)} working"
            if working else f"All {len(sorted_results)} failed"
        )

        if self._new_source:
            self._new_test_finished(bool(working))
        if not sorted_results:
            return

        # Build url→ProviderURL map so we keep stats
        url_map = {pu.url.rstrip("/"): pu for pu in self._provider_urls}

        new_order: List[ProviderURL] = []
        for url, success, _ms, _ in sorted_results:
            pu = url_map.get(url.rstrip("/"))
            if pu:
                # Update cumulative stats
                if success:
                    pu.success_count += 1
                else:
                    pu.failure_count += 1
                new_order.append(pu)

        # Assign fresh priorities
        for i, pu in enumerate(new_order):
            pu.priority = i

        self._provider_urls = new_order
        self._rebuild_url_list()

        # Auto-fetch account info if at least one URL worked
        if working:
            self._fetch_account_info()
