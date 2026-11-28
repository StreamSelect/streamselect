"""The Watch Queue as a Discover shelf (design "Discover as Your Dashboard", DQ4).

The queue in its own order, as posters: films and series only. A queued episode
shows as its series, once; a queued live channel stays in the sidebar queue. The
queue is a record of what the user chose, so the global exclusions do not thin it
(DR-0007's record-view exemption); only an entry that cannot play now (a hidden
source, an orphaned or reused stream id) is left out.
"""

from __future__ import annotations

from streamselect.core.discovery_engine import ContentCard, _dedup_cards, _to_card


def get_queue_cards(session, limit: int = 30, fav_ids=None, queue_ids=None, watched_ids=None,
                    liked_ids=None, progress_map=None, excluded_provider_ids=None) -> list[ContentCard]:
    """The first *limit* playable films and series in the watch queue, in queue order.

    Args:
        session: An open SQLAlchemy session.
        limit: How many cards at most.
        fav_ids, queue_ids, watched_ids, liked_ids, progress_map: The card badges'
            status sets, as every Discover shelf takes them.
        excluded_provider_ids: Hidden (inactive or expired) sources.

    Returns:
        One card per title, in the order the user queued them.
    """
    from streamselect.core.database import ChannelDB, MetadataDB
    from streamselect.core.repositories.queue import WatchQueueRepository

    ids = list(dict.fromkeys(      # queue order; an episode's entry is its series, kept once
        e.channel_id for e in WatchQueueRepository(session).get_all(
            hidden_provider_ids=set(excluded_provider_ids or ()))
        if e.available and e.channel is not None and e.media_type in ("movie", "series")))
    raw: list[ContentCard] = []
    cards: list[ContentCard] = []
    for start in range(0, len(ids), 200):          # a few batches until *limit* distinct titles
        chunk = ids[start:start + 200]
        rows = {ch.id: (ch, meta) for ch, meta in session.query(ChannelDB, MetadataDB)
                .outerjoin(MetadataDB, ChannelDB.metadata_id == MetadataDB.id)
                .filter(ChannelDB.id.in_(chunk))}
        raw += [_to_card(*rows[i], fav_ids, queue_ids, watched_ids, liked_ids, progress_map)
                  for i in chunk if i in rows]
        cards = _dedup_cards(raw)
        if len(cards) >= limit:
            break
    return cards[:limit]
