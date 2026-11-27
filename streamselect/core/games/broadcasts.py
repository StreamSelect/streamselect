"""Other broadcasts on now: what the Sports view shows under a league's On now.

Design "Other Broadcasts On Now" (owner, 2026-11-27). The finder stores every
timed listing that names a league but no teams and joined no game
(``game_broadcasts``, :class:`~streamselect.core.games.finder.Broadcast`); this
reads the ones on air for the view, off the UI thread, as frozen DTOs:

* on air: from its start to the guide's stop time, or for a channel name (which
  states no end) to its start plus the sport's usual game length;
* visible sources only (a disabled or expired source is never shown);
* one listing two leagues match goes to the more specific one, the longer league
  word ("NBA G League" is G League, not NBA; OB-Q12);
* one card per league, title and start: the same programme on several channels is
  one card with several channels (OB-Q10).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Optional

from sqlalchemy import select

from streamselect.core.database import ChannelDB
from streamselect.core.games.listing_text import norm
from streamselect.core.games.models import GameBroadcastDB
from streamselect.core.games.read import GameFeedDTO


@dataclass(frozen=True)
class BroadcastChannel:
    channel_id: str
    region: str
    #: What the play line names: a guide programme's channel, or a channel's package.
    station: str
    #: The channel's own name and collection, for the tooltip.
    name: str
    collection: str


@dataclass(frozen=True)
class BroadcastDTO:
    sport: str
    league: str
    title: str
    start_utc: datetime
    stop_utc: Optional[datetime]
    from_guide: bool
    channels: tuple[BroadcastChannel, ...]

    @property
    def league_key(self) -> str:
        return f"{self.sport}/{self.league}"


def load_broadcasts(session, sports: Mapping, hidden_provider_ids: set[str],
                    now: datetime) -> list[BroadcastDTO]:
    """The stored broadcasts on air at *now* (UTC-naive), earliest first.

    *sports*: sport key -> its settings (``usual_length`` bounds a channel name's broadcast).
    """
    rows = session.execute(select(GameBroadcastDB).where(GameBroadcastDB.sport.in_(list(sports)),
                                                         GameBroadcastDB.start_utc <= now)).scalars().all()
    on = [r for r in rows if now < (r.stop_utc or r.start_utc + sports[r.sport].usual_length)]
    # The more specific league claims a listing two leagues of one sport match.
    best: dict[tuple, int] = {}
    for r in on:
        k = (r.sport, r.channel_id, r.start_utc)
        best[k] = max(best.get(k, 0), r.word_len)
    on = [r for r in on if r.word_len == best[(r.sport, r.channel_id, r.start_utc)]]
    chans = {cid: rest for cid, *rest in session.execute(
        select(ChannelDB.id, ChannelDB.provider_id, ChannelDB.name, ChannelDB.category, ChannelDB.detected_region,
               ChannelDB.detected_title, ChannelDB.detected_collection)
        .where(ChannelDB.id.in_({r.channel_id for r in on})))}
    cards: dict[tuple, list] = defaultdict(list)
    first: dict[tuple, GameBroadcastDB] = {}
    for r in sorted(on, key=lambda r: (r.start_utc, r.id)):
        ch = chans.get(r.channel_id)
        if ch is None or ch[0] in hidden_provider_ids:
            continue
        pid, name, cat, region, title, package = ch
        k = (r.sport, r.league, norm(r.title), r.start_utc)
        first.setdefault(k, r)
        if all(c.channel_id != r.channel_id for c in cards[k]):
            # The play line's one naming rule (GameFeedDTO.title): a guide channel by its own
            # name, a channel by its package without the region head, a bare country by name.
            station = GameFeedDTO(r.channel_id, name or "", cat or "", r.from_guide, channel_collection=cat or "",
                                  region=region or "", own_name=title or "", package=package or "").title
            cards[k].append(BroadcastChannel(r.channel_id, region or "", station or name or "", name or "",
                                             cat or ""))
    return [BroadcastDTO(r.sport, r.league, r.title, r.start_utc, r.stop_utc, r.from_guide, tuple(cards[k]))
            for k, r in first.items() if cards[k]]
