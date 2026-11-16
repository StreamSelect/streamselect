"""What the system-tray icon says and lists — pure, so it is tested without Qt.

Settled in the "Tray Mode" design (TQ1-TQ14, owner 2026-11-16): the menu lists
what is playing, then the user's alerted items for the next 12 hours (live first,
at most five), and notifications can be paused for an hour, until tomorrow, or
until turned back on. Everything time-based takes ``now`` (UTC-naive, like every
stored time) and never reads the clock underneath.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from streamselect.core.epg_utils import to_local
from streamselect.core.time_display import clock_text

#: How far ahead the menu looks (TQ3).
HORIZON = timedelta(hours=12)
#: The most alerted items the menu lists (TQ3).
MENU_LIMIT = 5

#: Stored pause value meaning "until I turn them back on".
PAUSE_INDEFINITE = "indefinite"
PAUSE_HOUR = "hour"
PAUSE_TOMORROW = "tomorrow"

#: The notification kinds a sender can mark, each with its own switch (TQ2).
KIND_WATCH = "watch"      # EPG Watch Alerts and new episodes
KIND_GAME = "game"        # Sports event alerts
KIND_UPDATE = "update"    # a new StreamSelect release
KINDS = (KIND_WATCH, KIND_GAME, KIND_UPDATE)


@dataclass(frozen=True)
class TrayItem:
    """One alerted item in the menu: when, what, and where a click goes."""

    start_utc: datetime
    title: str
    detail: str            # league, or channel name
    target: str            # a ``navigate_to`` target, e.g. "view:sports"
    live: bool = False
    #: What a click on a LIVE item also plays: the game's preferred feed, or the
    #: programme's channel. None for upcoming items, which only open the app.
    channel_id: str | None = None

    @property
    def plays(self) -> str | None:
        """The channel a click starts, or None (owner, 2026-11-16: live only)."""
        return self.channel_id if self.live else None

    def label(self) -> str:
        when = "LIVE" if self.live else clock_text(to_local(self.start_utc))
        return f"{when}   {self.title}  ·  {self.detail}" if self.detail else f"{when}   {self.title}"


def menu_items(items: list[TrayItem], now: datetime) -> list[TrayItem]:
    """Live items first, then upcoming within :data:`HORIZON`, at most :data:`MENU_LIMIT`.

    The same programme can reach the list twice (two rules, two sources of the
    same game); a repeated title at the same start is shown once.
    """
    keep = [i for i in items if i.live or now <= i.start_utc <= now + HORIZON]
    keep.sort(key=lambda i: (not i.live, i.start_utc))
    seen: set[tuple[str, datetime]] = set()
    out: list[TrayItem] = []
    for item in keep:
        key = (item.title.casefold(), item.start_utc)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) == MENU_LIMIT:
            break
    return out


def pause_value(choice: str, now: datetime) -> str:
    """The stored pause for a menu *choice*: an ISO UTC end, or :data:`PAUSE_INDEFINITE`.

    "Until tomorrow" ends at the next local midnight, expressed in UTC.
    """
    if choice == PAUSE_INDEFINITE:
        return PAUSE_INDEFINITE
    if choice == PAUSE_HOUR:
        return (now + timedelta(hours=1)).isoformat()
    if choice == PAUSE_TOMORROW:
        local = to_local(now)
        midnight = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return (now + (midnight - local)).isoformat()
    raise ValueError(f"unknown pause choice {choice!r}")


def paused_until(value: str, now: datetime) -> datetime | None | str:
    """The pause in force: its UTC end, :data:`PAUSE_INDEFINITE`, or ``None`` (not paused).

    An unreadable or past value is "not paused" — a pause that cannot be read
    must not silence alerts forever.
    """
    if not value:
        return None
    if value == PAUSE_INDEFINITE:
        return PAUSE_INDEFINITE
    try:
        end = datetime.fromisoformat(value)
    except ValueError:
        return None
    return end if end > now else None


def pause_text(value: str, now: datetime) -> str:
    """How the pause reads in the tooltip and menu, or "" when not paused."""
    until = paused_until(value, now)
    if until is None:
        return ""
    if until == PAUSE_INDEFINITE:
        return "Notifications paused"
    return f"Notifications paused until {clock_text(to_local(until))}"


def tooltip(alert_count: int, playing: list[str], pause: str) -> str:
    """The icon's tooltip (TQ8): name, what plays, how many alerts, and any pause."""
    parts = ["StreamSelect"]
    if playing:
        parts.append(f"Playing {playing[0]}" + (f" (+{len(playing) - 1})" if len(playing) > 1 else ""))
    if alert_count:
        parts.append(f"{alert_count} alert{'' if alert_count == 1 else 's'} in the next 12 hours")
    if pause:
        parts.append(pause)
    return " · ".join(parts)
