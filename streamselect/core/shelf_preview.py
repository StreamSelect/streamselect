"""What a collapsed Discover shelf shows as a tile: four posters and a title count.

Design "Discover's Collapsed Shelves" (A, Tiles): a tile shows the shelf's NEWEST
additions (SQ3), so it also says what is new in it, and how many titles it holds
after the user's exclusions, one per title however many copies (SQ6). Asked for
only when a tile scrolls into view (SQ4).

Genre, year, decade and category shelves have a newest-first query here. Every
other shelf (Top Rated, a featured person, a service, your lists) previews its
own first four, through the one card dispatcher, with no count.
"""

from __future__ import annotations

from sqlalchemy import func, text

from streamselect.core.discovery_engine import (
    ContentCard, _apply_adult_filter, _apply_prefix_filter, _apply_provider_exclusion, _dedup_cards, _to_card,
)
from streamselect.core.filter_utils import normalize_genre

_NEWEST_POOL = 40      # rows read to find four distinct titles after the cross-source collapse


def _predicate(shelf_key: str, include_live: bool):
    """The row filter for a shelf with a newest-first preview, else ``None``."""
    from streamselect.core.database import ChannelDB
    from streamselect.core.platform_shelves import PLATFORM_SHELF_MEDIA_TYPES

    kind, _, value = shelf_key.partition(":")
    films = ChannelDB.media_type.in_(["movie", "series"])
    if kind == "genre":
        return [films, ChannelDB.detected_genres.isnot(None), text(
            "EXISTS (SELECT 1 FROM json_each(channels.detected_genres) AS je WHERE je.value = :g)"
        ).bindparams(g=normalize_genre(value))]
    if kind == "year":
        return [films, ChannelDB.detected_release_year == int(value)]
    if kind == "decade":
        return [films, ChannelDB.detected_release_year.between(int(value), int(value) + 9)]
    if kind == "collection":
        group = func.coalesce(ChannelDB.detected_collection_group, ChannelDB.detected_collection)
        return [group == value] + ([] if include_live else [ChannelDB.media_type.in_(PLATFORM_SHELF_MEDIA_TYPES)])
    return None


def shelf_preview(session, config, shelf_key: str, *, fk: dict, af: dict, ek: dict,
                  n: int = 4) -> tuple[list[ContentCard], int | None]:
    """A tile's posters and size.

    Args:
        session: An open session.
        config: The application ``Config``.
        shelf_key: The shelf's key.
        fk, af, ek: The scoping kwargs every Discover shelf query takes.
        n: How many cards.

    Returns:
        ``(cards, count)``: the newest *n* titles and the shelf's title count, or the
        shelf's own first *n* and ``None`` where there is no newest-first query.
    """
    from streamselect.core.database import ChannelDB, MetadataDB
    from streamselect.gui.discover_workers import fetch_cards_for_key

    pred = _predicate(shelf_key, bool(config.discover_show_live_collections))
    if pred is None:
        return fetch_cards_for_key(session, config, shelf_key, n, sk={}, fk=fk, af=af, ek=ek)[:n], None

    def scoped(q):
        q = q.filter(ChannelDB.is_hidden == False, *pred)  # noqa: E712
        q = _apply_prefix_filter(q, fk.get("excluded_prefixes"), fk.get("include_uncategorized", True),
                                 fk.get("excluded_content_types"), fk.get("excluded_keywords"),
                                 fk.get("excluded_categories"))
        q = _apply_adult_filter(q, af.get("adult_mode", "all"), af.get("force_adult_provider_ids"))
        return _apply_provider_exclusion(q, ek.get("excluded_provider_ids"), ek.get("dead_signal_streak_floor"))

    rows = (scoped(session.query(ChannelDB, MetadataDB)
                   .outerjoin(MetadataDB, ChannelDB.metadata_id == MetadataDB.id))
            .order_by(ChannelDB.detected_added.desc()).limit(_NEWEST_POOL).all())
    count = scoped(session.query(
        func.count(func.distinct(func.coalesce(ChannelDB.content_key, ChannelDB.id))))).scalar()
    return _dedup_cards([_to_card(ch, meta) for ch, meta in rows])[:n], int(count or 0)
