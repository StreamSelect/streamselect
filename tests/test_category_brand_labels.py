"""A streaming brand leading a label is the platform; MULTI is the audio form.

Before: "|MULTI| NETFLIX KIDS" became the collection "Multi Netflix Kids" with no
platform tag, because the platform vocabulary only matched a whole piece. The
same held for NETFLIX 4K / CHRISTMAS / ASIA, AMAZON PRIME (29k rows on a large
library), AMAZONE PRIME 4K and APPLE+. The owner's rule: the platform is the
brand, the rest is a category that crosses platforms, a quality is its own tag,
and MULTI is language/audio — so it crosses platforms too.
"""

from __future__ import annotations

import pytest

from streamselect.core.category_platforms import split_leading_brand
from streamselect.core.config import Config
from streamselect.core.region_codes import normalize_region_code
from streamselect.core.tag_decomposer import decompose


def _tags(category):
    return {(t, v) for t, v, _c in decompose("provider_category", category, config=Config())}


def _collections(category):
    return {v for t, v in _tags(category) if t == "collection"}


@pytest.mark.parametrize("category, platform, rest", [
    ("|MULTI| NETFLIX KIDS", "Netflix", ("platform", "Kids")),
    ("|MULTI| NETFLIX CHRISTMAS", "Netflix", ("collection", "Christmas")),
    ("|MULTI| NETFLIX ASIA", "Netflix", ("collection", "Asia")),
    ("|MULTI| NETFLIX 4K", "Netflix", ("quality", "4K / UHD")),
    ("|MULTI| AMAZON PRIME", "Amazon Prime", None),
    ("|MULTI| AMAZONE PRIME 4K", "Amazon Prime", ("quality", "4K / UHD")),
    ("|MULTI| APPLE+", "Apple TV+", None),
    ("|EN| APPLE TV+", "Apple TV+", None),
    ("|NL| DISNEY+ / NATGEO", "Disney+", ("collection", "Natgeo")),
    ("|NL| DISNEY +", "Disney+", None),
    ("|NL| DISNEYTV+", "Disney+", None),
])
def test_brand_is_the_platform_and_the_rest_is_its_own(category, platform, rest):
    tags = _tags(category)
    assert ("platform", platform) in tags
    if rest:
        assert rest in tags
    # The brand never survives inside a collection name.
    assert not any(platform.split()[0].upper() in c.upper() for c in _collections(category))


def test_a_quality_after_the_brand_leaves_no_collection():
    assert _collections("|MULTI| NETFLIX 4K") == set()


def test_decoration_after_the_brand_is_not_a_category():
    assert _collections("TUBI ᴿᴬᵂ") == set()
    assert ("platform", "Tubi") in _tags("TUBI ᴿᴬᵂ")


def test_multi_is_the_audio_form_not_collection_text():
    tags = _tags("|MULTI| NETFLIX")
    assert ("format", "Multi") in tags
    assert ("subtitle", "Multi") in tags
    assert "Multi" not in _collections("|MULTI| NETFLIX")


def test_disney_4k_stays_unassigned_until_verified():
    assert not {v for t, v in _tags("|MULTI| DISNEY 4K") if t == "platform"}
    assert ("platform", "Disney+") in _tags("|FR| DISNEY")  # bare piece: unchanged


@pytest.mark.parametrize("piece", ["SPORT RAW", "SKY NEWS", "KIDS MOVIES", "NETFLIX"])
def test_descriptor_groups_pay_tv_and_whole_brands_do_not_split(piece):
    assert split_leading_brand(piece, Config().filter_platform_groups) is None


def test_mult_is_a_typo_of_multi():
    assert normalize_region_code("MULT") == "MULTI"


def test_kids_after_a_brand_is_refaceted_like_any_kids_label(tmp_path):
    """The whole tag pipeline: Kids lands as genre on a movie, never platform."""
    from streamselect.core.migrations.tag_backfill import _collect_tags

    tags = {(t, v) for t, v, _f in _collect_tags(
        config=Config(), category="|MULTI| NETFLIX KIDS", source_category=None,
        detected_prefix="MULTI", detected_quality=None, detected_region=None,
        detected_year=None, raw_data=None, media_type="movie")}
    assert ("platform", "Netflix") in tags
    assert ("platform", "Kids") not in tags
    assert ("genre", "Kids") in tags


def test_v17_collector_selects_brand_and_multi_labels(tmp_path):
    from streamselect.core.database import ChannelDB, Database
    from streamselect.core.migrations.tag_backfill import TagBackfillTask

    db = Database(f"sqlite:///{tmp_path}/brand.db")
    db.create_tables()
    with db.session_scope() as s:
        for cid, cat in [("nk", "|MULTI| NETFLIX KIDS"), ("ap", "|EN| AMAZON PRIME"),
                         ("mu", "|MULTI| SOMETHING"), ("de", "|DE| FILME")]:
            s.add(ChannelDB(id=cid, source_id=cid, provider_id="p", name=cid,
                            media_type="movie", category=cat))
    ids = TagBackfillTask(db, Config())._collect_channel_ids_brand_label(Config())
    assert sorted(ids) == ["ap", "mu", "nk"]
