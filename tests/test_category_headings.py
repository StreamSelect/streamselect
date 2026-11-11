"""A continent heading is not a country; "NA" is North America.

One source files its live lineup as "<continent>| <country>": "AM| CANADA HD",
"AM| BRAZIL", "AM| AUSTRALIA". Read as a code, AM is Armenia, so all 1,125 rows
under it were stored region AM and tagged Armenian (the "CA-FR" French-Canadian
rows included). Headings are found by COUNTING the countries a source files
under a head, never by a list — measured: headings carry 4-17, a real country 1.

Separately, "NA" in IPTV labels is North America ("NA| HOCKEY LEAGUE",
"ARIRANG (NA)" feeds): 262 rows were stored Namibian, one of which was.
"""

from __future__ import annotations

import pytest

from streamselect.core.category_headings import detect_headings, masks_country
from streamselect.core.config import Config
from streamselect.core.region_codes import REGION_FULL_NAMES, is_country_code
from streamselect.core.tag_decomposer import decompose

AMERICAS = ["AM| CANADA HD", "AM| BRAZIL", "AM| ARGENTINA", "AM| CARIBBEAN"]


def _tags(category, headings=frozenset()):
    return {(t, v) for t, v, _c in decompose("provider_category", category,
                                              config=Config(), headings=headings)}


class TestCounting:

    def test_a_head_over_three_countries_is_a_heading(self):
        assert detect_headings(AMERICAS) == {"AM"}

    def test_a_head_over_one_country_is_not(self):
        # The other source's only AM category: Armenia, filed as Armenia.
        assert detect_headings(["AM| ARMENIA", "DE| GERMANY", "DE| FILME"]) == frozenset()

    def test_two_countries_is_below_the_threshold(self):
        assert detect_headings(["CH| SWITZERLAND", "CH| CHINA / HONGKONG"]) == frozenset()

    def test_spellings_of_one_country_count_once(self):
        # GERMANY → "GER" and DE are the same country, not two.
        assert detect_headings(["DE| GERMANY", "DE| GERMANY HD", "DE| FILME"]) == frozenset()


class TestMasking:

    @pytest.mark.parametrize("category, headings, masked", [
        ("AM| CANADA HD", frozenset(), True),        # a different country follows
        ("AM| CARIBBEAN", frozenset({"AM"}), True),  # the source says AM is a heading
        ("AM| CARIBBEAN", frozenset(), False),       # no evidence either way
        ("AM| ARMENIA", frozenset(), False),         # the country IS Armenia
        ("SK| SOUTH KOREA", frozenset(), True),      # not Slovakia
        ("DE| GERMANY", frozenset(), False),
        ("AF| ZIMBABWE", frozenset({"AF"}), False),  # Africa is no country to lose
    ])
    def test_masks_country(self, category, headings, masked):
        assert masks_country(category, headings) is masked

    def test_continent_and_language_codes_are_not_countries(self):
        assert is_country_code("AM") and is_country_code("SK")
        assert not any(is_country_code(c) for c in ("AF", "LAT", "AR", "NA"))


class TestTags:

    def test_americas_folder_is_canada_not_armenia(self):
        tags = _tags("AM| CANADA HD", frozenset({"AM"}))
        assert ("language", "Armenian") not in tags
        assert ("region", "AM") not in tags
        assert ("region", "CAN") in tags

    def test_a_countryless_americas_folder_needs_the_source_count(self):
        assert ("language", "Armenian") in _tags("AM| CARIBBEAN")
        assert ("language", "Armenian") not in _tags("AM| CARIBBEAN", frozenset({"AM"}))

    def test_armenia_is_still_armenia(self):
        assert ("language", "Armenian") in _tags("AM| ARMENIA")

    def test_na_is_north_america_and_implies_no_language(self):
        tags = _tags("NA| HOCKEY LEAGUE")
        assert ("region", "NA") in tags
        assert not {t for t in tags if t[0] == "language"}
        assert REGION_FULL_NAMES["NA"] == "North America"
        assert REGION_FULL_NAMES["NAM"] == "Namibia"


@pytest.fixture()
def db(tmp_path):
    from streamselect.core.database import Database

    database = Database(f"sqlite:///{tmp_path}/headings.db")
    database.create_tables()
    return database


def _add(db, cid, provider, name, category):
    from streamselect.core.database import ChannelDB

    with db.session_scope() as s:
        s.add(ChannelDB(id=cid, source_id=cid, provider_id=provider, name=name,
                        media_type="live", category=category))


def test_ingestion_and_retag_end_to_end(db):
    """Driven through update_detected_prefixes() and the v16 targeted re-tag.

    Fails against the pre-fix code: the Canada and Caribbean rows stored AM and
    carried language:Armenian; the hockey row was Namibian and English.
    """
    from streamselect.core.database import ChannelDB, ContentTagDB, TagDB
    from streamselect.core.migrations import tag_backfill_targets as targets
    from streamselect.core.migrations.tag_backfill import TagBackfillTask
    from streamselect.core.repositories import RepositoryFactory

    _add(db, "ca", "a", "CTV LETHBRIDGE HD", "AM| CANADA HD")
    _add(db, "br", "a", "|BR| COMBATE HD", "AM| BRAZIL")
    _add(db, "ar", "a", "|AR| TYC SPORTS", "AM| ARGENTINA")
    _add(db, "cb", "a", "CCN TV6", "AM| CARIBBEAN")
    _add(db, "hy", "a", "NA| ACADIE-BATHURST TITAN", "NA| HOCKEY LEAGUE")
    _add(db, "am", "b", "ARMENIA 1", "AM| ARMENIA")  # another source: real Armenia

    with db.session_scope() as s:
        RepositoryFactory(s).channels.update_detected_prefixes(provider_id=None)
    with db.session_scope() as s:
        stored = {c.id: (c.detected_prefix, c.detected_region) for c in s.query(ChannelDB)}
    assert stored["ca"] == (None, "CAN")
    assert stored["cb"] == (None, None)
    assert stored["hy"][1] == "NA"
    assert stored["am"][1] == "AM"

    task = TagBackfillTask(db, Config())
    ids = targets.heading_ids(db, targets.headings(db))
    assert {"ca", "cb", "hy"} <= set(ids) and "am" not in ids
    task._process_batch(sorted(ids) + ["am"], Config(), targets.headings(db))

    def tags(cid):
        with db.session_scope() as s:
            return {(t.type, t.value) for t in s.query(TagDB)
                    .join(ContentTagDB, ContentTagDB.tag_id == TagDB.id)
                    .join(ChannelDB, ChannelDB.channel_key == ContentTagDB.channel_key)
                    .filter(ChannelDB.id == cid)}

    assert ("language", "Armenian") not in tags("ca") | tags("cb")
    assert ("region", "CAN") in tags("ca")
    assert ("language", "English") not in tags("hy")
    assert ("language", "Armenian") in tags("am")
