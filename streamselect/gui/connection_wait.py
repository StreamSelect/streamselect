"""Wait for a source to free a connection, then start the title (Source Analytics Q7).

A source at its connection limit refuses a play with HTTP 458/509. When StreamSelect
itself holds nothing from that source, the slot is almost always a stream that
just ended and that the source is still counting — a user timed one source holding
one for ~22 minutes. Instead of a dead-end "Stream did not start", the user gets
a wait: the account endpoint (which uses no stream slot) is checked every
:data:`POLL_MS`, the title starts on its own when ``active_cons`` drops below
``max_connections``, and the wait is recorded so the Analytics tab can say how
long this source usually takes to free up.

One wait at a time per host. Starting any other play cancels it (``arm`` calls
:func:`cancel`), and so does the notification's Cancel button. The account
check reuses ``FetchAccountInfoThread`` — the editor's own fetch path — so URL
cycling and its outcome recording stay in one place.

**What a hold is measured from (owner, 2026-11-16).** A source holds a
connection from when OUR last stream from it closed, not from when it refused
the next play, and pressing Play again mid-wait is the same hold, not a new one:
measured from the refusal, a 16-minute hold was stored as 91 s. So each hold
keeps a :class:`HoldLedger` — when our stream ended (:func:`note_stream_ended`),
the first refusal, and how many checks and refused plays we sent — carried
across a cancel for :data:`CARRY_S`, and recorded when a connection frees, by
the wait's own check or by a play that starts (:func:`note_started`). The
recorded end-to-free times then decide when the first check goes out: just
before this source usually lets go, instead of every 30 s from the start.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QObject, QTimer
from loguru import logger

from streamselect.core.repositories import RepositoryFactory

#: How often the account endpoint is checked while waiting (user report, Q7: 30 s).
POLL_MS = 30_000
#: Past this the source is not merely counting an ended stream; stop waiting.
GIVE_UP_AFTER_S = 60 * 60
#: A wait cancelled by a new play is continued by a refusal on the same source
#: within this long: pressing Play again belongs to the same hold.
CARRY_S = 5 * 60
#: The first check goes out this long before the source usually frees one.
EARLY_S = 60


@dataclass
class HoldLedger:
    """One hold on one source, from our stream's end to a free connection."""

    provider_id: str
    refused_at: datetime            # the first refusal (UTC-naive)
    ended_at: datetime | None       # when our last stream from the source closed
    checks: int = 0                 # account checks sent
    plays: int = 1                  # plays the source refused
    #: Monotonic time the wait was cancelled, while the ledger waits to be continued.
    cancelled_at: float | None = None


def note_stream_ended(host: Any, provider_id: str | None) -> None:
    """A stream that played from *provider_id* closed now: where its hold begins."""
    if provider_id:
        host.__dict__.setdefault("_source_stream_ended", {})[provider_id] = datetime.utcnow()


def _ledger_for(host: Any, provider_id: str) -> HoldLedger | None:
    """The hold a refusal on *provider_id* continues, if one was cancelled recently."""
    ledger = host.__dict__.get("_hold_ledger")
    if (ledger is None or ledger.provider_id != provider_id or ledger.cancelled_at is None
            or time.monotonic() - ledger.cancelled_at > CARRY_S):
        return None
    return ledger


def note_started(host: Any, provider_id: str | None) -> None:
    """A play from *provider_id* started: a hold still open on it ends here.

    This is the hold a user resolves by pressing Play again rather than waiting.
    """
    ledger = _ledger_for(host, provider_id) if provider_id else None
    if ledger is not None:
        host.__dict__.pop("_hold_ledger", None)
        _record_hold(host, ledger, datetime.utcnow())


def _record_hold(host: Any, ledger: HoldLedger, freed_at: datetime) -> None:
    seconds = int((freed_at - ledger.refused_at).total_seconds())
    after_end = (f"{int((freed_at - ledger.ended_at).total_seconds())} s after our stream ended"
                 if ledger.ended_at else "our stream's end unknown")
    logger.info("connection hold on {}: free {} ({} s after the first refusal; {} checks, {} plays)",
                ledger.provider_id, after_end, seconds, ledger.checks, ledger.plays)
    try:
        host._run_query(lambda repos: repos.playback_events.record_hold(
                            ledger.provider_id, ledger.refused_at, seconds, ended_at=ledger.ended_at,
                            freed_at=freed_at, checks=ledger.checks, plays=ledger.plays),
                        lambda _r: None, commit=True,
                        on_error=lambda e: logger.warning("could not record the hold: {}", e))
    except Exception:
        logger.exception("could not record the connection hold")


def first_check_ms(typical_s: int | None, ended_at: datetime | None, now: datetime) -> int:
    """How long to wait before the first account check.

    With no recorded holds: :data:`POLL_MS`. Otherwise until :data:`EARLY_S`
    before this source usually frees a connection, counted from our stream's
    end (or from now when that is unknown), and never sooner than POLL_MS.
    """
    if typical_s is None:
        return POLL_MS
    since_end = (now - ended_at).total_seconds() if ended_at else 0
    return max(POLL_MS, int((typical_s - EARLY_S - since_end) * 1000))

#: Cancelled waits whose account check is still out: a QThread whose Python
#: wrapper is collected while it runs takes the process down, so the wait that
#: owns it stays referenced until the check returns.
_RETIRED: set = set()


def minutes_text(seconds: float) -> str:
    """A wait as people say it: "under a minute", "22 min"."""
    return "under a minute" if seconds < 60 else f"{round(seconds / 60)} min"


class _Wait(QObject):
    """One wait: the poll timer, the in-flight account check, the notification."""

    def __init__(self, host: Any, attempt: Any, source: str, ledger: HoldLedger) -> None:
        super().__init__()
        self.host, self.attempt, self.source, self.ledger = host, attempt, source, ledger
        self.started = time.monotonic()
        self.notif_id: str | None = None
        self._thread = None
        self.timer = QTimer(self)
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self.poll)

    @property
    def refused_at(self) -> datetime:
        return self.ledger.refused_at

    @refused_at.setter
    def refused_at(self, value: datetime) -> None:
        self.ledger.refused_at = value

    def poll(self) -> None:
        if self.timer.interval() != POLL_MS:    # the first check was scheduled later
            self.timer.setInterval(POLL_MS)
        if self._thread is not None:            # the previous check is still out
            return
        if time.monotonic() - self.started > GIVE_UP_AFTER_S:
            self._give_up()
            return
        from streamselect.gui.provider_editor_workers import FetchAccountInfoThread
        try:
            with self.host.db.session_scope(commit=False) as session:
                repos = RepositoryFactory(session)
                provider = repos.providers.to_model(repos.providers.get_by_id(self.attempt.provider_id))
        except Exception:
            logger.opt(exception=True).warning("connection wait: could not load the source")
            return
        self._thread = FetchAccountInfoThread(provider)
        self._thread.finished.connect(self.on_checked)
        self.ledger.checks += 1
        self._thread.start()

    def on_checked(self, success: bool, info: Any) -> None:
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.wait(2000)                   # run() has emitted; let it return
        _RETIRED.discard(self)
        if self.host.__dict__.get("_connection_wait") is not self:   # cancelled meanwhile
            return
        if not success or not isinstance(info, dict):
            logger.info("connection wait: account check failed ({}); trying again", info)
            return
        in_use, limit = info.get("active_cons", 0), info.get("max_connections", 1)
        logger.info("connection wait on {}: {} of {} connections in use", self.source, in_use, limit)
        if in_use < limit:
            self._freed()

    def _freed(self) -> None:
        cancel(self.host)
        self.host.__dict__.pop("_hold_ledger", None)
        freed_at = datetime.utcnow()
        seconds = int((freed_at - self.refused_at).total_seconds())
        _record_hold(self.host, self.ledger, freed_at)
        self.host.status(f"{self.source} freed a connection after {minutes_text(seconds)} — "
                         f"starting {self.attempt.channel_name}", ms=6000)
        self.host.play_channel_by_id(self.attempt.channel_id)

    def _give_up(self) -> None:
        cancel(self.host)
        self.host.__dict__.pop("_hold_ledger", None)
        self.host.notification_manager.show(
            title="Stopped waiting for a connection",
            message=f"{self.source} still had every connection in use after "
                    f"{minutes_text(GIVE_UP_AFTER_S)}. Try {self.attempt.channel_name} again later.",
            type="warning", auto_dismiss_ms=10000)


def begin(host: Any, attempt: Any) -> bool:
    """Start waiting for a free connection on *attempt*'s source. Returns whether it did.

    Declines (and the caller shows its usual failure toast) for a play with no
    channel identity, and when StreamSelect is itself streaming from the source — then
    the slot is ours, and waiting would wait on ourselves.
    """
    if attempt is None or not attempt.provider_id or not attempt.record_failure:
        return False
    pid = attempt.provider_id
    try:
        key = host.player_manager.resolve_key(pid)
        ours = [h for h in host.player_manager.connection_accountant.holders(pid) if h.holder_id != key]
    except Exception:
        logger.opt(exception=True).debug("connection wait: could not read our own connections")
        return False
    if ours:
        return False
    cancel(host)
    now = datetime.utcnow()
    ledger = _ledger_for(host, pid)
    if ledger is not None:                     # Play pressed again mid-hold: same hold
        ledger.plays += 1
        ledger.cancelled_at = None
    else:
        ledger = HoldLedger(pid, now, host.__dict__.get("_source_stream_ended", {}).get(pid))
    host._hold_ledger = ledger
    typical = _typical_hold(host, pid)
    delay_ms = first_check_ms(typical, ledger.ended_at, now)
    source = host._provider_display_name(pid)
    wait = _Wait(host, attempt, source, ledger)
    host._connection_wait = wait
    if typical is None:
        when = f"Checking every {POLL_MS // 1000} s"
    else:
        when = (f"It usually frees one {minutes_text(typical)} after a stream ends, so the "
                f"first check is in {minutes_text(delay_ms / 1000)}")
    wait.notif_id = host.notification_manager.show(
        title=f"Waiting for a connection on {source}",
        message=f"{source} has every connection in use — usually a stream that just ended "
                f"and is still being counted. {when}; "
                f"{attempt.channel_name} starts as soon as one frees up.",
        type="info", dismissible=False, actions=[("Cancel", lambda: cancel(host))])
    host.status(f"Waiting for a free connection on {source} to start {attempt.channel_name}…", ms=0)
    logger.info("connection wait on {}: first check in {} s (typical hold {}; play {} of this hold)",
                source, delay_ms // 1000, f"{typical} s" if typical is not None else "unknown",
                ledger.plays)
    wait.timer.start(delay_ms)
    return True


def _typical_hold(host: Any, provider_id: str) -> int | None:
    """This source's recorded end-to-free median; a tiny table, read in place."""
    try:
        with host.db.session_scope(commit=False) as session:
            return RepositoryFactory(session).playback_events.typical_hold_after_end(provider_id)
    except Exception:
        logger.opt(exception=True).warning("connection wait: could not read past holds")
        return None


def cancel(host: Any) -> None:
    """Stop the host's wait, if any, and take its notification down."""
    wait = host.__dict__.pop("_connection_wait", None)
    if wait is None:
        return
    wait.ledger.cancelled_at = time.monotonic()   # a refusal soon after continues it
    wait.timer.stop()
    if wait._thread is not None:
        _RETIRED.add(wait)
    if wait.notif_id is not None:
        host.notification_manager.dismiss(wait.notif_id)
