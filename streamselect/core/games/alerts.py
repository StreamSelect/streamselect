"""Event alerts: "tell me before this event / every Wild event / whenever these two meet".

Stored in the ONE watch-rule table (``alert_patterns``, the settled "one list"
rule and its guard) under their own ``pattern_type`` so the two dozen EPG/VOD
readers of keyword rules never see them (Sports Desk rev 4, SV-Q42):

* ``pattern_value`` — the side(s), joined by :data:`SEP`
* ``match_mode`` — ``"any"`` for one side, ``"all"`` for both sides
* ``description`` — a ``game_key`` for a one-event alert (it expires with that
  event), empty for a standing rule

Matching reads stored games only, never channel names.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from sqlalchemy import select

from streamselect.core.database import AlertPatternDB
from streamselect.core.games.finder import SportSettings
from streamselect.core.games.read import OVER, GameDTO, game_key, game_state
from streamselect.core.playback_models import PlaybackEventDB
from streamselect.core.watchlist_matching import ALL_WORDS, ANY_WORD

PATTERN_TYPE = "event"
SEP = " | "
#: The three kinds the bell offers (owner, SV-Q26).
THIS_EVENT, EITHER_SIDE, THESE_TWO = "this_event", "either_side", "these_two"


@dataclass(frozen=True)
class EventAlert:
    """One stored event-alert rule."""

    id: str
    sides: tuple[str, ...]
    mode: str                     # ALL_WORDS or ANY_WORD
    event: str                    # a game_key for a one-event alert, else ""

    @property
    def label(self) -> str:
        if self.event:
            return " vs ".join(self.sides)
        if self.mode == ANY_WORD:
            return self.sides[0]
        return f"{self.sides[0]} vs {self.sides[1]}"

    @property
    def detail(self) -> str:
        """The "Watching for" line's tail: what the rule covers."""
        if self.event:
            return "this event"
        return "every event" if self.mode == ANY_WORD else "whenever they meet"

    def matches(self, game: GameDTO) -> bool:
        if self.event:
            return self.event == game_key(game)
        teams = {game.team_a, game.team_b}
        if self.mode == ANY_WORD:
            return any(s in teams for s in self.sides)
        return set(self.sides) <= teams


def rule_for(kind: str, game: GameDTO, side: str = "") -> EventAlert:
    """The rule a bell choice makes (id empty until stored)."""
    if kind == THIS_EVENT:
        return EventAlert("", (game.team_a, game.team_b), ALL_WORDS, game_key(game))
    if kind == EITHER_SIDE:
        return EventAlert("", (side,), ANY_WORD, "")
    return EventAlert("", (game.team_a, game.team_b), ALL_WORDS, "")


def load_alerts(session) -> list[EventAlert]:
    rows = session.execute(select(AlertPatternDB).where(AlertPatternDB.pattern_type == PATTERN_TYPE)
                           .order_by(AlertPatternDB.created_at)).scalars()
    return [EventAlert(r.id, tuple((r.pattern_value or "").split(SEP)),
                       r.match_mode or ALL_WORDS, r.description or "") for r in rows]


def add_alert(session, rule: EventAlert) -> str:
    """Store *rule* unless an identical one exists; returns its id."""
    value = SEP.join(rule.sides)
    for existing in load_alerts(session):
        if existing.sides == rule.sides and existing.mode == rule.mode and existing.event == rule.event:
            return existing.id
    new_id = str(uuid.uuid4())
    session.add(AlertPatternDB(id=new_id, name=rule.label, pattern_type=PATTERN_TYPE,
                               pattern_value=value, match_mode=rule.mode, description=rule.event,
                               applies_to="events", action="notify", is_enabled=True))
    return new_id


def remove_alerts(session, ids: Iterable[str]) -> None:
    for row in session.execute(select(AlertPatternDB).where(AlertPatternDB.id.in_(list(ids)))).scalars():
        session.delete(row)


def alerts_for(game: GameDTO, alerts: Iterable[EventAlert]) -> list[EventAlert]:
    """The rules that cover *game* (one bell can be lit by several)."""
    return [a for a in alerts if a.matches(game)]


#: How long after the start an "it's starting" notice may still fire (a poll can be late).
START_GRACE = 600


def due_notices(games: Iterable[GameDTO], alerts: list[EventAlert], now, lead_minutes: int,
                sent: set[str]) -> list[tuple[str, GameDTO, str]]:
    """The notices to send now: ``(notice key, game, title)``, each once (SV-Q43).

    One ``lead_minutes`` before an alerted event starts ("Starting in 15 minutes"),
    then again at its start ("Starting now"). ``sent`` holds the keys already
    sent; a lead of 0 sends only the start notice.
    """
    out = []
    for g in games:
        if not alerts_for(g, alerts):
            continue
        key = game_key(g)
        since_start = (now - g.start_utc).total_seconds()
        if 0 <= since_start <= START_GRACE and f"start|{key}" not in sent:
            out.append((f"start|{key}", g, "Starting now"))
        elif (lead_minutes > 0 and g.start_utc - timedelta(minutes=lead_minutes) <= now < g.start_utc
              and f"lead|{key}" not in sent):
            mins = max(1, round((g.start_utc - now).total_seconds() / 60))
            out.append((f"lead|{key}", g, f"Starting in {mins} minute{'' if mins == 1 else 's'}"))
    return out


#: A play that began up to this long before an event's start counts as watching it
#: (tuning in for the warm-up).
WATCH_EARLY = timedelta(minutes=15)
#: A one-event rule is deleted this long after its event started: past any event's length.
EVENT_RULE_KEEP = timedelta(hours=12)


def watched_game_ids(session, games: list[GameDTO]) -> set[int]:
    """Games the user has started watching: a play of one of its channels from
    :data:`WATCH_EARLY` before its start onward."""
    by_channel: dict[str, list[GameDTO]] = {}
    for g in games:
        for f in g.playable:
            by_channel.setdefault(f.channel_id, []).append(g)
    if not by_channel:
        return set()
    since = min(g.start_utc for g in games) - WATCH_EARLY
    rows = session.execute(
        select(PlaybackEventDB.channel_id, PlaybackEventDB.started_at)
        .where(PlaybackEventDB.channel_id.in_(list(by_channel)),
               PlaybackEventDB.started_at >= since,
               PlaybackEventDB.outcome.in_(("started", "dropped")))).all()
    return {g.id for cid, at in rows for g in by_channel[cid] if at >= g.start_utc - WATCH_EARLY}


def waiting_events(games: Iterable[GameDTO], alerts: list[EventAlert], now: datetime,
                   settings: dict[str, SportSettings], watched: set[int]) -> list[GameDTO]:
    """The alerted events Watch Alerts lists: upcoming or live, not watched yet.

    Each event is its own item (two games between the same teams on back-to-back
    days are two items). One goes by itself when it is over, marked finished, or
    watched; the rule that matched it stays.
    """
    return [g for g in games
            if g.id not in watched and g.sport in settings and alerts_for(g, alerts)
            and game_state(g, now, settings[g.sport]) != OVER]


def expired_event_rules(alerts: Iterable[EventAlert], now: datetime) -> list[str]:
    """Ids of one-event rules whose event started more than :data:`EVENT_RULE_KEEP` ago."""
    out = []
    for a in alerts:
        if not a.event:
            continue
        try:
            start = datetime.fromisoformat(a.event.rsplit("|", 1)[1])
        except (IndexError, ValueError):
            continue
        if now - start > EVENT_RULE_KEEP:
            out.append(a.id)
    return out
