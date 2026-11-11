"""Owner's unrecognized-prefix review (2026-11-11): compounds, TM, operators, aliases.

- A compound prefix's locale part was never tagged: "PB-PREM" (a premium 24/7
  lineup — PREM is a tier, like VIP/GOLD) left 728 of 733 rows with no locale.
- "TM" is Tamil in IPTV labels; ~3,500 Tamil rows were tagged Russian because
  the language groups read TM as Turkmenistan (now TKM).
- Operator lineups (T2 = Tele2 NL, ES-C, PT-NOS…) are platforms; FRQ/CA-FR are
  Quebec French; KURD/SRB/SKR/MH/BANGLA/ZIMBABWE/SU are spellings of known codes.
"""

from __future__ import annotations

import pytest

from streamselect.core.config import Config
from streamselect.core.region_codes import REGION_FULL_NAMES, normalize_region_code
from streamselect.core.tag_decomposer import decompose_name_parse


def _tags(prefix):
    return {(t, v) for t, v, _c in decompose_name_parse(
        detected_prefix=normalize_region_code(prefix), detected_quality=None,
        detected_region=None, detected_year=None, config=Config())}


@pytest.mark.parametrize("prefix, expected", [
    ("PB-PREM", ("language", "Indian")),
    ("IN-PREM", ("region", "IN")),
    ("TM-PREM", ("language", "Indian")),
    ("AR-4K", ("language", "Arabic")),
    ("IN-EN", ("language", "English")),
])
def test_a_compound_prefix_carries_its_locale(prefix, expected):
    assert expected in _tags(prefix)


def test_a_subtitle_compound_still_names_no_audio_language():
    assert not {v for t, v in _tags("AR-SUB") if t == "language"}


def test_tm_is_tamil_not_turkmenistan():
    tags = _tags("TM")
    assert ("language", "Indian") in tags
    assert ("language", "Russian") not in tags
    assert REGION_FULL_NAMES["TM"] == "Tamil"
    assert REGION_FULL_NAMES["TKM"] == "Turkmenistan"
    assert ("language", "Russian") in _tags("TKM")


@pytest.mark.parametrize("prefix, platform", [
    ("T2", "Pay TV"), ("ES-C", "Pay TV"), ("PT-NOS", "Pay TV"), ("NL-CW", "Pay TV"),
    ("V+", "Pay TV"), ("VIA", "Other Streaming"), ("UK-BBCI", "Other Streaming"),
])
def test_operator_lineups_are_platforms(prefix, platform):
    assert ("platform", platform) in _tags(prefix)


def test_operator_compound_keeps_its_language():
    assert ("language", "Spanish") in _tags("ES-AV")


@pytest.mark.parametrize("raw, code", [
    ("FRQ", "QFR"), ("CA-FR", "QFR"), ("KURD", "KU"), ("SRB", "RS"),
    ("SKR", "KR"), ("MH", "MR"), ("BANGLA", "BN"), ("ZIMBABWE", "ZW"),
])
def test_confirmed_spellings_normalize(raw, code):
    assert normalize_region_code(raw) == code


def test_suriname_has_a_name():
    assert REGION_FULL_NAMES["SU"] == "Suriname"


def test_v19_collector_selects_compound_and_changed_codes(tmp_path):
    from streamselect.core.database import ChannelDB, Database
    from streamselect.core.migrations.tag_backfill_targets import prefix_review_ids

    db = Database(f"sqlite:///{tmp_path}/review.db")
    db.create_tables()
    with db.session_scope() as s:
        for cid, prefix, region in [("pb", "PB-PREM", None), ("tm", None, "TM"),
                                    ("t2", "T2", "NL"), ("de", "DE", "DE")]:
            s.add(ChannelDB(id=cid, source_id=cid, provider_id="p", name=cid,
                            media_type="live", detected_prefix=prefix, detected_region=region))
    assert sorted(prefix_review_ids(db)) == ["pb", "t2", "tm"]


def test_a_quality_led_pipe_prefix_is_parsed_and_its_service_tagged(tmp_path):
    """"|4K-DS| Deadpool 4K": DS is Disney+, AP Amazon Prime (one source's
    4K-<service> code). The pipe pattern required a letter first, so the marker
    stayed in 91 titles and the service was lost."""
    from streamselect.core.database import ChannelDB, Database
    from streamselect.core.migrations.tag_backfill_targets import quality_led_prefix_ids
    from streamselect.core.repositories import RepositoryFactory

    db = Database(f"sqlite:///{tmp_path}/ds.db")
    db.create_tables()
    with db.session_scope() as s:
        for cid, name in [("ds", "|4K-DS| Deadpool 4K"), ("ap", "|4K-AP| Reacher 4K"),
                          ("ar", "|AR-4K| Test")]:
            s.add(ChannelDB(id=cid, source_id=cid, provider_id="p", name=name,
                            media_type="movie", category="|MULTI| X"))
    with db.session_scope() as s:
        RepositoryFactory(s).channels.update_detected_prefixes()
    with db.session_scope() as s:
        got = {c.id: (c.detected_prefix, c.detected_title) for c in s.query(ChannelDB)}
    assert got["ds"] == ("4K-DS", "Deadpool")
    assert got["ap"] == ("4K-AP", "Reacher")
    assert got["ar"] == ("AR-4K", "Test")
    assert ("platform", "Disney+") in _tags("4K-DS")
    assert ("platform", "Amazon Prime") in _tags("4K-AP")
    assert sorted(quality_led_prefix_ids(db)) == ["ap", "ds"]
