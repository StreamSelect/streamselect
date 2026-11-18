"""Which row a source's channel is: (source, type, number), not the text of an id.

A source numbers its content in more than one series: an Xtream source gives
live channels and movies stream numbers, and series their own, separate
numbers. Channel ids used to be built as ``"{provider_id}_{number}"``, so live
stream 25529 and series 25529 got the same id: a full refresh threw one away as
a "duplicate" (about 2,074 a refresh, measured 2026-11-17), and every launch's
live-only refresh wrote the live channel over the stored series. A queued
"Jeeves And Wooster" became "TNT HD".

The database now manages identity: a unique index on (provider_id, media_type,
source_id) (``channel_index_policy.identity_index_sql``), and every refresh asks
it which id a channel already has (:class:`ChannelIds`) before anything else
keys on ids. The id itself is only a handle:

- an existing row keeps its id forever, whatever its form, so every stored
  reference (queue, ratings, history, settings) stays valid with no migration;
- a new row gets :func:`typed_channel_id` — readable, because people copy it
  from the details pane and paste it into search, but not parsed: code that
  needs the source, type or number reads the columns. The one reader of an
  id's text is ``queue.provider_id_of``, recovering the source of a queue row
  whose channel is gone; both forms keep the source before the last ``_``.

A queue row also stores the type and number it was queued as, so
:func:`repoint_queue_entries` moves one that now points at another type's row
(the live channel that overwrote its series) back to the right row once the
refresh has stored it.
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy import select

from streamselect.core.database import ChannelDB, WatchQueueDB

#: The columns that say which channel a row is (the unique index's columns).
IDENTITY_COLUMNS = ("provider_id", "media_type", "source_id")


def typed_channel_id(provider_id: str, media_type: str, source_id: str) -> str:
    """The id a NEW row gets: ``"{provider_id}_{media_type}-{source_id}"``.

    The ``-`` keeps the last ``_`` between the source and the rest, so ids of
    both forms read the same way to a person. Never parse it.
    """
    return f"{provider_id}_{media_type}-{source_id}"


class ChannelIds:
    """One source's (type, number) -> id, read once per refresh."""

    def __init__(self, provider_id: str, known: dict[tuple[str, str], str]):
        self.provider_id = provider_id
        self._known = known

    @classmethod
    def load(cls, session, provider_id: str) -> "ChannelIds":
        rows = session.execute(
            select(ChannelDB.media_type, ChannelDB.source_id, ChannelDB.id)
            .where(ChannelDB.provider_id == provider_id)).all()
        return cls(provider_id, {(mt or "", str(sid)): cid for mt, sid, cid in rows})

    def id_for(self, media_type: str, source_id) -> str:
        """The stored row's id for this channel, or a new typed id (remembered,
        so a second listing of the same channel in this refresh gets the same)."""
        # MediaType is plain strings today; .value guards a plugin passing an Enum,
        # which hashes by name and would never match the stored value.
        key = (str(getattr(media_type, "value", media_type) or ""), str(source_id))
        found = self._known.get(key)
        if found is None:
            found = self._known[key] = typed_channel_id(self.provider_id, key[0], key[1])
        return found


def resolve_channel_ids(db, provider_id: str, channels: list) -> list:
    """Give each fetched channel the id of the row it already is, or a new one.

    Runs before the refresh de-duplicates by id, so two channels that only
    shared a number (live 25529, series 25529) stay two channels.
    """
    with db.session_scope(commit=False) as session:
        ids = ChannelIds.load(session, provider_id)
    for ch in channels:
        ch.id = ids.id_for(ch.media_type, ch.source_id)
    return channels


def repoint_queue_entries(session, provider_id: str) -> int:
    """Point each channel-grain queue row back at the row it was queued as.

    A row whose channel is a different type from what was queued (live
    "TNT HD" where the series "Jeeves And Wooster" was queued), or whose
    channel is gone, moves to this source's row with the queued type and
    number, when one exists. Its place, date added and name are kept.

    Returns:
        How many rows moved (committed).
    """
    ids = ChannelIds.load(session, provider_id)
    known = ids._known
    moved = 0
    rows = (session.query(WatchQueueDB, ChannelDB)
            .outerjoin(ChannelDB, ChannelDB.id == WatchQueueDB.channel_id)
            .filter(WatchQueueDB.episode_id.is_(None), WatchQueueDB.media_type != "",
                    WatchQueueDB.source_id != "").all())
    for row, ch in rows:
        if ch is not None and (ch.provider_id != provider_id or ch.media_type == row.media_type):
            continue                    # another source's, or already the right type
        if ch is None and not row.channel_id.startswith(provider_id + "_"):
            continue                    # a gone row of another source
        target = known.get((row.media_type, str(row.source_id)))
        if target and target != row.channel_id:
            logger.info("Watch queue: {!r} moved back to its {} row {} (was {})",
                        row.channel_name, row.media_type, target, row.channel_id)
            row.channel_id = target
            moved += 1
    if moved:
        session.commit()
    return moved
