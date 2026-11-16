"""The window's handle on a source refresh running in its own process.

Stands where ``ProviderLoadThread`` stood for ``RefreshQueueManager``: the same
constructor, the same ``progress(int, int, str)`` and ``finished(bool, str)``
signals, and the same attributes the post-refresh handler reads (``kind``,
``provider_id``, ``fetch_epg``, ``prefix_stats``). The work itself runs in
:func:`streamselect.core.refresh_worker.run_refresh`, whose docstring says why.

The child is started with ``spawn`` everywhere, so it never inherits the
window's Qt state, and is a daemon, so quitting the app ends it. A refresh
killed mid-write loses only the batch in flight: SQLite rolls back the open
transaction, and the next refresh redoes the work.

Messages arrive on a pipe polled from a main-thread timer: ``poll()`` works on
every platform, where a socket notifier does not on Windows pipes.
"""

from __future__ import annotations

import multiprocessing

from loguru import logger
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from streamselect.core.refresh_worker import build_request, run_refresh

#: How often the window reads the child's messages.
POLL_MS = 100


class ProviderLoadProcess(QObject):
    """One source refresh in a child process."""

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, provider, db, *, separators=None, language_groups=None,
                 quality_groups=None, platform_groups=None, regional_groups=None,
                 kind: str = "full", parent=None):
        super().__init__(parent)
        self.kind = kind
        self.provider_id = provider.id
        self.fetch_epg = True
        self.prefix_stats: dict | None = None
        self._request = build_request(provider.id, str(db.engine.url), kind, {
            "separators": separators, "language_groups": language_groups,
            "quality_groups": quality_groups, "platform_groups": platform_groups,
            "regional_groups": regional_groups,
        })
        self._proc = None
        self._conn = None
        self._done = False
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        ctx = multiprocessing.get_context("spawn")
        self._conn, child_end = ctx.Pipe(duplex=False)
        self._proc = ctx.Process(target=run_refresh, args=(self._request, child_end),
                                 name=f"refresh-{self.kind}", daemon=True)
        self._proc.start()
        child_end.close()           # the child holds its own copy
        self._timer.start()

    def isRunning(self) -> bool:
        return self._proc is not None and self._proc.is_alive()

    def stop(self) -> None:
        """End the child now (quit, or a cancelled refresh)."""
        if self.isRunning():
            self._proc.terminate()
            self._proc.join(2)
        self._finish(False, "The refresh was stopped")

    def _poll(self) -> None:
        try:
            while self._conn.poll():
                message = self._conn.recv()
                if message[0] == "progress":
                    self.progress.emit(*message[1:])
                elif message[0] == "finished":
                    _tag, ok, text, stats = message
                    self.prefix_stats = stats
                    self._finish(bool(ok), text)
                    return
        except (EOFError, OSError):
            pass                     # the child closed its end; checked below
        if not self._proc.is_alive():
            self._finish(False, "The refresh stopped unexpectedly "
                                f"(exit code {self._proc.exitcode})")

    def _finish(self, ok: bool, text: str) -> None:
        if self._done:
            return
        self._done = True
        self._timer.stop()
        if self._conn is not None:
            self._conn.close()
        if self._proc is not None:
            self._proc.join(5)
            if not ok:
                logger.warning("refresh process for {} ended: {}", self.provider_id, text)
        self.finished.emit(ok, text)
