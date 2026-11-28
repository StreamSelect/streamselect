"""Discover's "Recommended for You" shelf, remembered between visits.

Working out recommendations is the slowest thing Discover does (~5 s on a large
library), and its answer rarely changes between visits. So the last answer is kept
with the profile (``config.discover_recommended_cache``) beside a fingerprint of
everything the answer depends on: your likes and dislikes, favourites, what you
last played, the catalogue's size and newest addition, the exclusions and sources
in scope, and the scoring settings. Same fingerprint: the kept titles are shown
and nothing is worked out. A different one: the kept titles still show at once
(``stale_cards``), and the fresh answer replaces them when it is ready.

Every exclusion axis comes from
:func:`~streamselect.core.preference_engine.recommendation_scope`, the one place
that knows what a recommendation may contain (the shelf assembles none itself).
"""

from __future__ import annotations

import hashlib

from sqlalchemy import func

from streamselect.core.discovery_engine import ContentCard, _to_card


def fingerprint(session, config) -> str:
    """A short digest of every input the recommendations depend on."""
    from streamselect.core.database import ChannelDB, UserRatingDB
    from streamselect.core.preference_engine import RecScoringSettings, recommendation_scope

    ratings = session.query(func.count(UserRatingDB.channel_id), func.max(UserRatingDB.rated_at)).one()
    channels = session.query(func.count(ChannelDB.id), func.max(ChannelDB.detected_added),
                             func.max(ChannelDB.last_played)).one()
    favourites = session.query(func.count(ChannelDB.id)).filter(ChannelDB.is_favorite.is_(True)).scalar()
    scope = sorted((k, repr(sorted(map(str, v)) if isinstance(v, (list, set, frozenset, tuple)) else v))
                   for k, v in recommendation_scope(session, config).items())
    raw = repr((tuple(map(str, ratings)), tuple(map(str, channels)), favourites, scope,
                repr(RecScoringSettings.from_config(config))))
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _cards_in_order(session, ids: list[str]) -> list[ContentCard]:
    """Cards for *ids*, in that order (rows come back in id order otherwise)."""
    from streamselect.core.database import ChannelDB, MetadataDB

    order = {cid: n for n, cid in enumerate(ids)}
    rows = (session.query(ChannelDB, MetadataDB)
            .outerjoin(MetadataDB, ChannelDB.metadata_id == MetadataDB.id)
            .filter(ChannelDB.id.in_(list(order))).all())
    rows.sort(key=lambda pair: order.get(pair[0].id, len(order)))
    return [_to_card(ch, meta) for ch, meta in rows]


def stale_cards(session, config) -> list[ContentCard]:
    """The last recommendations kept, whatever has changed since (to show at once)."""
    return _cards_in_order(session, list((config.discover_recommended_cache or {}).get("ids") or []))


def is_current(session, config) -> bool:
    """True when the kept recommendations were worked out from today's inputs."""
    kept = config.discover_recommended_cache or {}
    return bool(kept.get("ids")) and kept.get("fp") == fingerprint(session, config)


def get_recommended(session, config, limit: int = 30) -> list[ContentCard]:
    """The Recommended shelf: the kept answer while it is current, else a fresh one.

    A fresh answer is kept (in memory here; the view saves the profile), so the next
    visit is instant until something it depends on changes.

    Args:
        session: An open session.
        config: The application ``Config``.
        limit: Maximum cards to return.

    Returns:
        Cards in score order; empty when there is not enough taste signal yet.
    """
    from streamselect.core.preference_engine import (
        RecScoringSettings, compute_weights, recommendation_scope, score_candidates, version_score,
    )

    fp = fingerprint(session, config)
    kept = config.discover_recommended_cache or {}
    if kept.get("fp") == fp and kept.get("ids"):
        return _cards_in_order(session, kept["ids"][:limit])

    settings = RecScoringSettings.from_config(config)
    weights = compute_weights(session, settings=settings)
    recs = [] if weights.is_empty() else score_candidates(
        session, weights, limit=limit,
        **recommendation_scope(session, config),
        version_scorer=lambda ch: version_score(ch, config),
        diversify_people=True,
        settings=settings,
    )
    ids = [sc.channel_id for sc in recs or ()]
    config.discover_recommended_cache = {"fp": fp, "ids": ids}
    return _cards_in_order(session, ids) if ids else []
