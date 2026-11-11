"""A streaming brand leading a category label: "NETFLIX KIDS" is Netflix + Kids.

A provider category splits on its pipes, and the platform vocabulary matched a
piece only when the WHOLE piece was a brand name. So ``"|MULTI| NETFLIX"`` was
Netflix, while ``"NETFLIX 4K"``, ``"NETFLIX KIDS"``, ``"NETFLIX CHRISTMAS"`` and
``"AMAZON PRIME 4K"`` fell through to collection text and carried no platform
at all (about 1,300 rows on a large library). The brand is the platform; what
follows it ("KIDS", "CHRISTMAS", "ASIA") is a category that crosses platforms,
and a quality ("4K") is already its own tag.

Only streaming brands lead this way. Content-descriptor groups ("Sports",
"Kids", "News"…) and the Pay TV group stay whole-token matches: "SPORT RAW" or
"SKY NEWS" are not a brand plus a category.
"""

from __future__ import annotations

import re

from streamselect.core.content_labels import CONTENT_DESCRIPTOR_GROUPS, CONTENT_TYPE_WORDS
from streamselect.core.quality_vocab import TIER_TOKENS

#: Groups whose aliases never lead a label.
_NOT_BRANDS: frozenset[str] = CONTENT_DESCRIPTOR_GROUPS | {"Pay TV"}

#: Aliases too broad to lead: "DISNEY 4K" mixes Fox catalogue with other
#: studios' titles, so it is not Disney+ until someone verifies what it holds.
#: A bare "DISNEY" piece keeps its whole-token meaning unchanged.
_NOT_LEADING: frozenset[str] = frozenset({"DISNEY"})


def split_leading_brand(
    piece: str, platform_groups: dict[str, list[str]],
) -> tuple[str, str] | None:
    """``("NETFLIX", "KIDS")`` for ``"NETFLIX KIDS"``; None when no brand leads.

    Args:
        piece: One pipe-delimited piece of a provider category.
        platform_groups: ``Config.filter_platform_groups``.

    Returns:
        ``(alias, rest)`` — the longest streaming-brand alias the piece starts
        with, and what follows it (possibly empty) — or None. A piece that IS the alias returns
        None: the whole-token match already handles it.
    """
    up = " ".join(piece.upper().split())
    aliases = sorted(
        (a.upper() for group, codes in platform_groups.items()
         if group not in _NOT_BRANDS for a in codes if a.upper() not in _NOT_LEADING),
        key=len, reverse=True,
    )
    if up in aliases:
        return None  # the piece IS a brand: the whole-token match handles it
    for alias in aliases:
        m = re.match(rf"{re.escape(alias)}(?=\s)\s+(.+)$", up)
        if m:
            # "/ NATGEO" → "NATGEO"; a tier ("SHAHID VIP 4K") is package
            # decoration, never a category — PPV stays, it is a content type.
            words = [w for w in m.group(1).split()
                     if w not in TIER_TOKENS or w in CONTENT_TYPE_WORDS]
            return alias, " ".join(words).lstrip("/&+- ")
    return None
