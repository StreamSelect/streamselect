"""Logging setup shared by the app and its short-lived worker processes.

The refresh worker (``core.refresh_worker``) runs in its own process, which
starts with loguru's default stderr sink only; it calls :func:`configure_logging`
so its lines land in the same log file, redacted the same way.
"""

from __future__ import annotations

import os

from loguru import logger

from streamselect.core.stream_diagnostics import _redact


def configure_logging(log_file: "str | None" = None) -> None:
    """Redact credentials on every record and write to the app's log file.

    Args:
        log_file: The file to write to; the app's own (:func:`active_log_file`)
            when omitted. A worker process is handed the window's, so it never
            resolves a home directory of its own.
    """

    # Redact credentials on EVERY record, before any sink sees it.
    #
    # An Xtream stream URL embeds the subscription's username and password —
    # `{base}/movie/{user}/{pass}/{id}.ext` — and `player_api.php` takes them
    # as `?username=…&password=…`. Seventy-one call sites log a URL. A scan of
    # one developer machine found many `username=` and many `password=`
    # occurrences sitting in `~/.config/streamselect/logs/` under a seven-day
    # retention, from ordinary use.
    #
    # Fixed HERE rather than at those 71 sites, and the distinction is the
    # whole point: `_redact` already existed and was already imported by
    # `main_window_streaming.py`, which called it at one of its five URL logs.
    # Patching call sites is how you get four out of five — it is the same
    # enumeration failure as the `refresh_theme()` sweep and the hand-listed
    # test stubs. A patcher cannot be forgotten by the next person to write a
    # `logger.info(f"... {url}")`, because they never have to know it exists.
    def _scrub(record):
        record["message"] = _redact(record["message"])

    logger.configure(patcher=_scrub)

    # DEBUG was hardcoded here, in the shipped app. Two logger.debug calls in
    # the raw-metadata parser fired many times each and produced 1.30M of
    # 1.44M lines — 330 MB across the retention window, which then held 8 days
    # of noise where it would otherwise hold 76 days of signal. The level is
    # now INFO by default and DEBUG on request, via STREAMSELECT_LOG_LEVEL, so a
    # support session can turn it up without a rebuild.
    level = os.environ.get("STREAMSELECT_LOG_LEVEL", "INFO").upper()
    if level not in {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}:
        level = "INFO"
    logger.add(
        log_file or active_log_file(),
        rotation="10 MB",
        retention="7 days",
        level=level,
    )


def active_log_file() -> str:
    """The log file the app writes to now."""
    from streamselect.core.log_paths import ACTIVE_LOG_NAME, log_directory

    return str(log_directory(create=True) / ACTIVE_LOG_NAME)
