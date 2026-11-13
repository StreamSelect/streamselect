"""Re-find stored games after the catalog or the guide changes, off the UI thread.

One worker (the finder writes, and SQLite has one writer); a request that
arrives while a run is in flight sets a flag and runs once more afterwards, so
a burst of refreshes costs at most two runs and the last one sees everything.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtCore import QObject, pyqtSignal
from loguru import logger

from streamselect.core.games.store import refresh_games

#: The first run waits this long after launch, off the start-up path.
GAME_TRACKER_LAUNCH_DELAY_MS = 15_000


class GameTracker(QObject):
    """Owns the game-finder worker; ``request()`` from any main-thread slot."""

    #: Emitted on the main thread after a run stored its games: league key -> Level 1 count.
    games_updated = pyqtSignal(object)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self._db = db
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="games")
        self._lock = threading.Lock()
        self._running = False
        self._again = False
        self._closed = False

    def request(self, *_args) -> None:
        """Run the finder now, or once more after the run in flight."""
        with self._lock:
            if self._closed:
                return
            if self._running:
                self._again = True
                return
            self._running = True
        self._pool.submit(self._run)

    def _run(self) -> None:
        while True:
            try:
                counts = refresh_games(self._db)
                self.games_updated.emit(counts)
            except Exception:
                logger.exception("Game finder run failed")
            with self._lock:
                if not self._again or self._closed:
                    self._running = False
                    return
                self._again = False

    def shutdown(self) -> None:
        with self._lock:
            self._closed = True
        self._pool.shutdown(wait=False, cancel_futures=True)
