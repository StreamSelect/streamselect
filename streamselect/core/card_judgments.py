"""Your judgment of each title on a Discover card: liked, disliked or not interested.

Owner: "content that I've rated should show my rating on it, so I know what I've
already seen." A judgment is stored per ROW (``user_ratings`` for like/dislike,
``channels.is_rec_suppressed`` for Not Interested) but belongs to the TITLE, so it
is collapsed at read on the stored ``content_key`` (CLAUDE.md "Judgment applies to
the title"): a title you disliked under one source shows it under every source.
One query for a page of cards, at the card dispatcher.
"""

from __future__ import annotations

from dataclasses import replace

from sqlalchemy import or_

from streamselect.core.content_identity import title_key


def with_judgments(session, cards: list) -> list:
    """*cards* with ``user_rating`` / ``is_rec_suppressed`` set from your judgments."""
    from streamselect.core.database import ChannelDB, UserRatingDB

    if not cards:
        return cards
    keys = {c.content_key for c in cards if c.content_key}
    ids = {c.channel_id for c in cards}
    rows = (session.query(ChannelDB.id, ChannelDB.content_key, UserRatingDB.rating, ChannelDB.is_rec_suppressed)
            .outerjoin(UserRatingDB, UserRatingDB.channel_id == ChannelDB.id)
            .filter(or_(ChannelDB.content_key.in_(keys), ChannelDB.id.in_(ids)))
            .filter(or_(UserRatingDB.rating.isnot(None), ChannelDB.is_rec_suppressed.is_(True)))
            .all())
    rating: dict[str, int] = {}
    suppressed: set[str] = set()
    for cid, key, r, supp in rows:
        k = title_key(key, cid)
        if r:            # a dislike anywhere outweighs a like elsewhere
            rating[k] = min(rating.get(k, 1), r)
        if supp:
            suppressed.add(k)
    out = []
    for c in cards:
        k = title_key(c.content_key, c.channel_id)
        r, s = rating.get(k, 0), k in suppressed
        out.append(replace(c, user_rating=r, is_rec_suppressed=s, is_liked=c.is_liked or r == 1)
                   if (r or s) else c)
    return out
