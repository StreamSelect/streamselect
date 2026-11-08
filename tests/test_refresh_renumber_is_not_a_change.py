"""A source that renumbers its list has not changed its channels.

Xtream ``num`` is a channel's position in the provider's list. One insertion
near the top shifts it on nearly every row after it: a real refresh flagged
284,590 of ~300k channels "changed" for that alone, re-parsed every name,
re-wrote every ``raw_data`` blob, and then crashed with "too many SQL
variables" when the whole id list reached ``StreamInfoRepository``.

These tests drive the real store path on a file database: a position-only
difference takes the cheap renumber write and keeps every derived field, a
real rename still counts as a change, and ``invalidate_changed`` survives an
id list longer than SQLite's variable limit.
"""
import sqlite3
from datetime import datetime, timedelta

from streamselect.core.database import ChannelDB, StreamInfoDB
from streamselect.core.provider_loader import _CATALOG_UPDATE_COLS
from streamselect.core.repositories import RepositoryFactory
from streamselect.core.repositories.channel_change_detection import diff_batch_for_upsert
from streamselect.core.repositories.channel_upsert import flush_channel_batch

CID = "p1_1001"


def _row(num, name="NHL | 01 - 7pm Golden Knights @ Bruins"):
    raw = {"num": num, "name": name, "stream_type": "live", "stream_id": 1001,
           "epg_channel_id": "", "category_id": "10"}
    row = {
        "id": CID, "source_id": "1001", "provider_id": "p1", "name": name,
        "stream_url": "http://example.com/live/u/p/1001.ts",
        "category": "US| HOCKEY PACKAGE", "category_id": "10", "logo_url": None,
        "epg_channel_id": None, "media_type": "live", "quality": "unknown",
        "is_adult": False, "raw_data": raw, "detected_tmdb_id": None,
        "detected_rating": None, "detected_added": None, "source_num": None,
        "source_category": None, "source_quality_flags": None,
    }
    try:
        row["source_num"] = int(num)
    except (TypeError, ValueError):
        pass
    assert set(_CATALOG_UPDATE_COLS) <= set(row), "row must carry every catalog column"
    return row


def _store(db, row, seen_at, title="parsed-before"):
    with db.session_scope() as s:
        flush_channel_batch(s, [row], _CATALOG_UPDATE_COLS, seen_at=seen_at)
    with db.session_scope() as s:
        s.get(ChannelDB, CID).detected_title = title


def _refresh(db, row, seen_at):
    """One store pass exactly as provider_loader runs it: diff, then flush."""
    with db.session_scope() as s:
        changed, unchanged, renumbered = diff_batch_for_upsert(s, [row], _CATALOG_UPDATE_COLS)
        flush_channel_batch(s, [row], _CATALOG_UPDATE_COLS, seen_at=seen_at,
                            unchanged_ids=unchanged, renumbered_ids=renumbered)
    return changed, unchanged, renumbered


def test_a_position_shift_is_renumbered_not_changed(db):
    t0 = datetime(2026, 11, 7, 18, 0)
    _store(db, _row(40), t0)

    t1 = t0 + timedelta(hours=1)
    changed, unchanged, renumbered = _refresh(db, _row(41), t1)

    assert changed == set(), "a list position feeds no detected_* field"
    assert renumbered == {CID} and unchanged == set()
    with db.session_scope() as s:
        ch = s.get(ChannelDB, CID)
        assert ch.source_num == 41
        assert ch.raw_data["num"] == 41 and isinstance(ch.raw_data["num"], int)
        assert ch.raw_data["stream_id"] == 1001, "the rest of raw_data is untouched"
        assert ch.detected_title == "parsed-before", "derived fields survive a renumber"
        assert ch.last_seen_at == t1, "presence still moves, or the pruner drops it"

    # The patched row now matches, so the next identical refresh writes nothing.
    changed, unchanged, renumbered = _refresh(db, _row(41), t1 + timedelta(hours=1))
    assert (changed, unchanged, renumbered) == (set(), {CID}, set())


def test_a_string_position_stays_a_string(db):
    t0 = datetime(2026, 11, 7, 18, 0)
    _store(db, _row("12"), t0)
    _, _, renumbered = _refresh(db, _row("13"), t0 + timedelta(hours=1))
    assert renumbered == {CID}
    with db.session_scope() as s:
        assert s.get(ChannelDB, CID).raw_data["num"] == "13"


def test_a_rename_with_a_shift_is_still_a_change(db):
    t0 = datetime(2026, 11, 7, 18, 0)
    _store(db, _row(40), t0)
    changed, _, renumbered = _refresh(
        db, _row(41, name="NHL | 01 - 12:30pm Panthers @ Capitals"), t0 + timedelta(hours=1))
    assert changed == {CID} and renumbered == set()
    with db.session_scope() as s:
        ch = s.get(ChannelDB, CID)
        assert ch.name == "NHL | 01 - 12:30pm Panthers @ Capitals"
        assert ch.detected_title is None, "a rename clears the old parse for re-derivation"


def test_invalidate_changed_survives_more_ids_than_sqlite_allows(db):
    _store(db, _row(1), datetime(2026, 11, 7, 18, 0))
    with db.session_scope() as s:
        RepositoryFactory(s).stream_info.upsert(CID, {"video": None, "audio": []}, source="played")

    ids = [CID] + [f"p1_missing_{i}" for i in range(2000)]
    with db.session_scope() as s:
        raw = s.connection().connection.dbapi_connection
        before = raw.getlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER)
        raw.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 999)
        try:
            s.get(ChannelDB, CID).name = "Something Else"
            assert RepositoryFactory(s).stream_info.invalidate_changed(ids) == 1
            assert RepositoryFactory(s).stream_info.get_many(ids) == {}
        finally:
            raw.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, before)
    with db.session_scope() as s:
        assert s.get(StreamInfoDB, CID) is None
