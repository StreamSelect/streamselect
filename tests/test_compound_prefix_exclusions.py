"""Compound prefixes obey Global Exclusions (user report).

``IN-CAM - Title`` and ``IN-TE - Title`` were stored as one literal prefix, so an
excluded ``IN`` or ``TE`` never matched them, and ``detected_region`` is only
consulted when there is no prefix at all. Runs on a real file database, because
the SQL predicate reads a stored column and the upgrade path has to fill it.
"""
from __future__ import annotations

import pytest

from streamselect.core.database import ChannelDB
from streamselect.core.filter_utils import channel_exclusion_criterion, is_channel_excluded
from streamselect.core.migrations.exclusion_code_backfill import ExclusionCodeBackfillTask
from streamselect.core.region_codes import code_family, exclusion_code
from streamselect.core.repositories import RepositoryFactory


@pytest.mark.parametrize("prefix, code", [
    ("IN-CAM", "IN"),         # a release label, so the place decides
    ("IN-PREM", "IN"),
    ("IN-TE", "TE"),          # a language part wins
    ("IN-EN", "EN"),
    ("IN-KA", "KN"),          # through the alias table
    ("IN-MA", "IN"),          # MA is Morocco here, never a language
    ("IN-UK", "IN"),          # two places: the first decides
    ("BLURAY-DE", "DE"),      # the code can come second
    ("CA-FR", "FR"),
    ("DE-BLURAY-DV", "DE"),
    ("UK-NOWTV", "UK"),
    ("PAK-PREM", "PAK"),
    ("AR-SUB", None),         # names the subtitles, not the audio
    ("CAR-AMP", None),        # nothing we can name
    ("IN", None),             # not compound: the prefix itself decides
    ("", None),
    (None, None),
])
def test_the_code_a_compound_is_judged_by(prefix, code):
    assert exclusion_code(prefix) == code


def _add(db, *prefixes):
    with db.session_scope() as session:
        for prefix in prefixes:
            session.add(ChannelDB(
                id=prefix, source_id=prefix, provider_id="p", name=f"{prefix} - Title",
                detected_prefix=prefix, detected_region="IN",
                detected_exclusion_code=exclusion_code(prefix),
            ))


def _visible(db, excluded) -> set[str]:
    with db.session_scope(commit=False) as session:
        return {
            cid for (cid,) in session.query(ChannelDB.id)
            .filter(channel_exclusion_criterion(set(excluded), ChannelDB))
        }


def test_indian_compounds_are_hidden_and_english_stays(file_db):
    _add(file_db, "IN-CAM", "IN-TE", "IN-PREM", "IN-EN", "UK-NOWTV", "IN")
    assert _visible(file_db, {"IN", "TE"}) == {"IN-EN", "UK-NOWTV"}


def test_excluding_english_hides_the_english_compound(file_db):
    _add(file_db, "IN-EN")
    assert _visible(file_db, {"EN"}) == set()


def test_language_wins_when_only_the_place_is_excluded(file_db):
    """The same rule a plain ``TE`` row with region IN already gets."""
    _add(file_db, "IN-TE")
    assert _visible(file_db, {"IN"}) == {"IN-TE"}


def test_blocking_the_exact_compound_still_works(file_db):
    """"Block [PREFIX]" stores the literal string."""
    _add(file_db, "IN-EN", "IN-CAM")
    assert _visible(file_db, {"IN-EN"}) == {"IN-CAM"}


def test_excluding_pakistan_covers_the_pak_spelling():
    assert exclusion_code("PAK-PREM") in code_family({"PK"})


@pytest.mark.parametrize("prefix, excluded", [
    ("IN-CAM", {"IN"}), ("IN-CAM", {"TE"}), ("IN-EN", {"IN"}), ("IN-EN", {"EN"}),
    ("IN-TE", {"TE"}), ("AR-SUB", {"AR"}), ("IN", {"IN"}), ("IN-EN", {"IN-EN"}),
])
def test_the_python_and_sql_predicates_agree(file_db, prefix, excluded):
    _add(file_db, prefix)
    assert is_channel_excluded(prefix, "IN", excluded) == (prefix not in _visible(file_db, excluded))


def test_ingestion_stores_the_code(file_db):
    with file_db.session_scope() as session:
        session.add(ChannelDB(id="x", source_id="x", provider_id="p", media_type="movie",
                              name="IN-CAM - Pehla Pyaar Doosri Baar (2026)"))
    with file_db.session_scope() as session:
        RepositoryFactory(session).channels.update_detected_prefixes()
    with file_db.session_scope(commit=False) as session:
        row = session.get(ChannelDB, "x")
        assert row.detected_prefix == "IN-CAM"
        assert row.detected_exclusion_code == "IN"


def test_the_backfill_fills_existing_rows_and_leaves_plain_ones(file_db):
    with file_db.session_scope() as session:
        for cid, prefix in (("a", "IN-CAM"), ("b", "IN-CAM"), ("c", "IN-EN"), ("d", "IN"), ("e", None)):
            session.add(ChannelDB(id=cid, source_id=cid, provider_id="p", name=cid, detected_prefix=prefix))
    assert _visible(file_db, {"IN"}) == {"a", "b", "c", "e"}, "the bug, before the backfill runs"

    ExclusionCodeBackfillTask(file_db).run(lambda *_: None, lambda: False)

    with file_db.session_scope(commit=False) as session:
        codes = {c.id: c.detected_exclusion_code for c in session.query(ChannelDB)}
    assert codes == {"a": "IN", "b": "IN", "c": "EN", "d": None, "e": None}
    assert _visible(file_db, {"IN"}) == {"c", "e"}
