"""Superscript decoration in a label is read as names read it; VIP/GOLD are tiers.

"NL| TELE2 VERMAAK ᴿᴬᵂ ᴳᴼᴸᴰ" became the collection "Tele2 Vermaak ᴿᴬᵂ ᴳᴼᴸᴰ"
with no quality: the category decomposer never ran the superscript reader the
name parser uses, so RAW (a quality — owner) was lost in 126 labels / 12.5k
rows. And VIP/GOLD sat in the platform table while quality_vocab.TIER_TOKENS
names them package tiers, so "LAT| MEXICO VIP" carried platform:VIP (1,724 rows).
"""

from __future__ import annotations

import pytest

from streamselect.core.config import Config
from streamselect.core.tag_decomposer import decompose


def _tags(category):
    return {(t, v) for t, v, _c in decompose("provider_category", category, config=Config())}


def test_superscript_raw_is_quality_and_leaves_the_collection():
    tags = _tags("NL| TELE2 VERMAAK ᴿᴬᵂ ᴳᴼᴸᴰ")
    assert ("quality", "RAW") in tags
    assert ("collection", "Tele2 Vermaak") in tags
    assert not any("ᴿ" in v or "ᴳ" in v for _t, v in tags)


@pytest.mark.parametrize("category", [
    "LAT| MEXICO VIP", "|AR| SHAHID VIP 4K", "|EN| PARAMOUNT+ PPV VIP",
    "NORWAY ᴳᴼᴸᴰ ᴿᴬᵂ", "|FR| VIP",
])
def test_vip_and_gold_are_never_a_platform_or_a_collection(category):
    tags = _tags(category)
    assert not {v for t, v in tags if t == "platform" and v in ("VIP", "GOLD")}
    assert not {v for t, v in tags if t == "collection" and v.upper() in ("VIP", "GOLD")}


def test_ppv_beside_a_tier_keeps_its_content_type():
    assert ("content_type", "ppv") in _tags("|EN| PARAMOUNT+ PPV VIP")


def test_shahid_vip_4k_is_shahid_in_4k():
    tags = _tags("|AR| SHAHID VIP 4K")
    assert ("platform", "Shahid") in tags and ("quality", "4K / UHD") in tags


def test_v18_collector_selects_decorated_and_tier_labels(tmp_path):
    from streamselect.core.database import ChannelDB, Database
    from streamselect.core.migrations.tag_backfill import TagBackfillTask

    db = Database(f"sqlite:///{tmp_path}/deco.db")
    db.create_tables()
    with db.session_scope() as s:
        for cid, cat in [("t2", "NL| TELE2 VERMAAK ᴿᴬᵂ ᴳᴼᴸᴰ"), ("mx", "LAT| MEXICO VIP"),
                         ("de", "|DE| FILME"), ("ac", "|ES| ACCIÓN")]:
            s.add(ChannelDB(id=cid, source_id=cid, provider_id="p", name=cid,
                            media_type="live", category=cat))
    assert sorted(TagBackfillTask(db, Config())._collect_channel_ids_decorated_label()) == ["mx", "t2"]
