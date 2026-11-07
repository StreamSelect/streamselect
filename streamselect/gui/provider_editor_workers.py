"""The Sources editor's background workers — the two threads that talk to a provider.

``FetchAccountInfoThread`` reads the account/subscription info (also reused by
``connection_wait``); ``TestAllURLsThread`` probes every address of a source
at once and diagnoses a total failure. No widgets here: each emits signals the
editor (main thread) turns into what the user sees.
"""
from __future__ import annotations

import asyncio
from typing import List

from PyQt6.QtCore import QThread, pyqtSignal
from loguru import logger

from streamselect.core.connection_diagnosis import diagnose
from streamselect.core.models import Provider
from streamselect.core.provider_probe import ProbeResult, probe_all_urls
from streamselect.gui.connection_diagnosis_text import format_probe_message


class FetchAccountInfoThread(QThread):
    """Fetches live account/subscription info from the Xtream auth endpoint."""

    finished = pyqtSignal(bool, object)  # success, info_dict | error_str

    def __init__(self, provider: Provider):
        super().__init__()
        self.provider = provider

    def run(self):
        try:
            asyncio.run(self._fetch())
        except Exception as e:
            self.finished.emit(False, str(e))

    async def _fetch(self):
        from streamselect.providers.factory import get_provider
        plugin = get_provider(self.provider.type)
        if not plugin or not hasattr(plugin, "fetch_account_info"):
            self.finished.emit(False, "Source type does not support account info")
            return
        info = await plugin.fetch_account_info(self.provider)
        if info:
            self.finished.emit(True, info)
        else:
            self.finished.emit(False, "No response from source")


class TestAllURLsThread(QThread):
    """Tests every URL simultaneously; emits a result per URL as they finish,
    then emits all_done with results sorted: successes (fastest first), failures last."""

    url_result = pyqtSignal(str, bool, int, str)  # url, success, ms, message
    all_done = pyqtSignal(list)                   # [(url, success, ms, message), ...]
    #: A DiagnosisReport, emitted alongside all_done. Carried separately because
    #: all_done's tuples are already formatted for display and have dropped the
    #: probe status and HTTP detail that the diagnosis is derived from — the
    #: information exists, it just stops here.
    diagnosis = pyqtSignal(object)

    def __init__(self, urls: List[str], username: str, password: str,
                 answered_before: frozenset = frozenset()):
        super().__init__()
        self.urls = urls
        self.username = username
        self.password = password
        #: Addresses known to have answered as an Xtream server earlier; see
        #: ``connection_diagnosis.diagnose``.
        self.answered_before = answered_before

    def run(self):
        try:
            asyncio.run(self._test_all())
        except Exception:
            # An empty result with no reason reads as "all of them failed".
            logger.exception("Testing all provider URLs failed")
            self.all_done.emit([])

    async def _test_all(self):
        def _emit(r: ProbeResult):
            # Streamed per-URL as each probe finishes (queued to the main thread).
            self.url_result.emit(r.url, r.success, r.latency_ms, format_probe_message(r))

        results = await probe_all_urls(
            self.urls, self.username, self.password, on_result=_emit
        )
        self.all_done.emit(
            [(r.url, r.success, r.latency_ms, format_probe_message(r)) for r in results]
        )
        # Diagnosed in core (no English there); phrased by the editor.
        self.diagnosis.emit(diagnose(results, self.answered_before))
