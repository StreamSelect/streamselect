"""Which rows each targeted tag re-run (versions 16-19) re-decomposes.

A version bump that changes how one kind of label or prefix is read only
needs the rows carrying it; these collectors name them, so a library already
at the previous version re-tags thousands of rows instead of the corpus.
``TagBackfillTask.run`` chooses between them by the stored version.
"""

from __future__ import annotations

import re

from sqlalchemy import or_, text

#: Prefix/region codes whose meaning changed in version 19 (old and new spellings).
PREFIX_REVIEW_CODES: tuple[str, ...] = (
    "TM", "TKM", "T2", "ONE", "SAT", "V+", "TF", "AZAM", "VIA", "VD", "TY", "PLAYER",
    "FRQ", "QFR", "KURD", "KU", "SRB", "RS", "SKR", "KR", "MH", "MR", "BANGLA", "BN",
    "ZIMBABWE", "ZW", "SU",
)

#: Labels that newly resolve to a platform in version 17.
_NEW_ALIASES = frozenset({"AMAZON PRIME", "AMAZONE PRIME", "PRIME VIDEO", "APPLE+", "APPLE TV",
                          "APPLE TV+", "HBO MAX", "DISNEY +", "DISNEYTV+"})


def headings(db) -> dict[str, frozenset[str]]:
    """``{provider_id: category headings}`` — one query, read once per run."""
    from streamselect.core.category_headings import headings_by_provider
    with db.session_scope(commit=False) as session:
        return headings_by_provider(session)


def _ids_with_labels(session, labels: list[str]) -> list[str]:
    from streamselect.core.database import ChannelDB
    ids: list[str] = []
    for i in range(0, len(labels), 500):  # bounded IN lists
        ids += [r[0] for r in session.query(ChannelDB.id)
                .filter(ChannelDB.category.in_(labels[i:i + 500]))]
    return ids


def _labels(session) -> list[str]:
    return [r[0] for r in session.execute(text(
        "SELECT DISTINCT category FROM channels WHERE COALESCE(category, '') != ''"))]


def heading_ids(db, by_provider: dict[str, frozenset[str]]) -> list[str]:
    """Rows under a masked category head, or carrying "NA" (version 16)."""
    from streamselect.core.category_headings import masks_country
    with db.session_scope(commit=False) as session:
        rows = session.execute(text(
            "SELECT id, provider_id, category, detected_prefix, detected_region"
            " FROM channels WHERE COALESCE(category, '') LIKE '%|%'"
            " OR detected_prefix = 'NA' OR detected_region = 'NA'")).all()
    return [cid for cid, pid, cat, prefix, region in rows
            if "NA" in (prefix, region) or (cat or "").strip().lstrip("|").upper().startswith("NA|")
            or masks_country(cat, by_provider.get(pid, frozenset()))]


def brand_label_ids(db, config) -> list[str]:
    """Rows whose label has a brand-led, MULTI or new-alias piece (version 17)."""
    from streamselect.core.category_platforms import split_leading_brand
    from streamselect.core.channel_name_utils import extract_audio_annotation
    from streamselect.core.filter_utils import _split_compound
    groups = config.filter_platform_groups
    with db.session_scope(commit=False) as session:
        hit = [lab for lab in _labels(session) if any(
            split_leading_brand(p, groups) or p.upper() in _NEW_ALIASES
            or extract_audio_annotation(p)[0] == "Multi" for p in _split_compound(lab))]
        return _ids_with_labels(session, hit)


def decorated_label_ids(db) -> list[str]:
    """Rows whose label carries superscript decoration or a tier word (version 18)."""
    from streamselect.core.channel_name_utils import _extract_superscript_attributes
    from streamselect.core.quality_vocab import TIER_TOKENS
    tier_re = re.compile(rf"\b({'|'.join(sorted(TIER_TOKENS))})\b", re.IGNORECASE)
    with db.session_scope(commit=False) as session:
        hit = [lab for lab in _labels(session) if tier_re.search(lab)
               or _extract_superscript_attributes(lab)[0] != lab]
        return _ids_with_labels(session, hit)


def prefix_review_ids(db) -> list[str]:
    """Rows with a compound prefix or a code whose meaning changed (version 19)."""
    from streamselect.core.database import ChannelDB
    with db.session_scope(commit=False) as session:
        return [r[0] for r in session.query(ChannelDB.id).filter(or_(
            ChannelDB.detected_prefix.like("%-%"),
            ChannelDB.detected_prefix.in_(PREFIX_REVIEW_CODES),
            ChannelDB.detected_region.in_(PREFIX_REVIEW_CODES)))]
