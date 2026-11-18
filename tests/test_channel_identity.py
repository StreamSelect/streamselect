"""The database decides which row a channel is: (source, type, number), never the id's text.

An Xtream source numbers series separately from live channels and movies, and
ids were built as "{source}_{number}": live 25529 and series 25529 shared one.
A full refresh dropped one as a "duplicate" (~2,074 a refresh), and every
live-only refresh wrote the live channel over the stored series — a queued
"Jeeves And Wooster" became "TNT HD" (owner's log, 2026-11-17).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import text

from streamselect.core.channel_index_policy import CHANNEL_IDENTITY_INDEX, identity_index_sql
from streamselect.core.database import ChannelDB, Database, WatchQueueDB
from streamselect.core.models import Channel, MediaType, Provider, StreamQuality
from streamselect.core.provider_loader import ProviderLoadThread
from streamselect.core.repositories.channel_identity import ChannelIds, typed_channel_id

PID = "prov-1"


def _provider() -> Provider:
    p = Provider.__new__(Provider)
    p.id, p.name, p.type, p.url = PID, "P", "xtream", "http://example.com"
    p.username, p.password, p.urls = "u", "p", []
    return p


def _ch(number: str, media_type: str, name: str) -> Channel:
    return Channel(id=f"{PID}_{number}", source_id=number, provider_id=PID, name=name,
                   stream_url=f"http://example.com/{media_type}/{number}", category="C",
                   category_id="1", media_type=media_type, quality=StreamQuality.HD, raw_data={})


def _refresh(db, channels, kind="full"):
    plugin = MagicMock()
    plugin.fetch_channels = AsyncMock(return_value=channels)
    plugin.fetch_account_info = None
    thread = ProviderLoadThread(_provider(), db, kind=kind)
    with patch("streamselect.core.provider_loader.get_provider", return_value=plugin):
        asyncio.run(thread.load_provider())


def _rows(db):
    with db.session_scope(commit=False) as s:
        return {(c.media_type, c.source_id): (c.id, c.name)
                for c in s.query(ChannelDB).filter(ChannelDB.provider_id == PID)}


def _seed_provider(db):
    from streamselect.core.database import ProviderDB
    with db.session_scope() as s:
        s.add(ProviderDB(id=PID, name="P", type="xtream", url="http://example.com",
                         username="u", password="p", is_active=True))


SERIES = _ch("25529", MediaType.SERIES, "EN - Jeeves And Wooster (1990)")
LIVE = _ch("25529", MediaType.LIVE, "LAT| TNT HD")


def test_a_series_and_a_live_channel_sharing_a_number_are_two_channels(db):
    _seed_provider(db)
    _refresh(db, [SERIES, LIVE])
    rows = _rows(db)
    assert rows[("series", "25529")][1] == "EN - Jeeves And Wooster (1990)"
    assert rows[("live", "25529")][1] == "LAT| TNT HD"
    assert rows[("series", "25529")][0] != rows[("live", "25529")][0]


def test_a_live_only_refresh_never_writes_over_the_series(db):
    _seed_provider(db)
    _refresh(db, [SERIES, LIVE])
    before = _rows(db)
    _refresh(db, [LIVE], kind="live_only")
    after = _rows(db)
    assert after[("series", "25529")] == before[("series", "25529")], "the series is untouched"
    assert after[("live", "25529")] == before[("live", "25529")], "the live row keeps its id"


def test_an_existing_row_keeps_its_old_id_and_its_user_data(db):
    """No stored reference has to change: old-form ids stay as they are."""
    _seed_provider(db)
    with db.session_scope() as s:
        s.add(ChannelDB(id=f"{PID}_945", source_id="945", provider_id=PID, name="UK| NEWS",
                        media_type="live", is_favorite=True, play_count=3))
    _refresh(db, [_ch("945", MediaType.LIVE, "UK| NEWS HD")])
    with db.session_scope(commit=False) as s:
        rows = s.query(ChannelDB).filter(ChannelDB.provider_id == PID).all()
        assert [(r.id, r.name, r.is_favorite, r.play_count) for r in rows] == [
            (f"{PID}_945", "UK| NEWS HD", True, 3)]


def test_a_new_channel_gets_a_readable_typed_id_that_search_finds(db):
    from streamselect.core.repositories.search_ranking import channel_text_search_predicate
    _seed_provider(db)
    _refresh(db, [SERIES])
    new_id = typed_channel_id(PID, "series", "25529")
    assert _rows(db)[("series", "25529")][0] == new_id == f"{PID}_series-25529"
    with db.session_scope(commit=False) as s:
        found = s.query(ChannelDB.id).filter(channel_text_search_predicate(new_id)).all()
        assert [r.id for r in found] == [new_id], "a copied id pasted into search finds it"


def test_ids_resolve_from_the_stored_type_and_number():
    ids = ChannelIds(PID, {("live", "25529"): f"{PID}_25529"})
    assert ids.id_for("live", 25529) == f"{PID}_25529"
    assert ids.id_for("series", "25529") == f"{PID}_series-25529"
    assert ids.id_for("series", "25529") == f"{PID}_series-25529", "stable within a refresh"


def test_a_queue_entry_overwritten_by_a_live_channel_moves_back_to_its_series(db):
    """The damaged state on real data: the queue row (series, 25529) points at
    the old-form row a live refresh turned into TNT HD."""
    _seed_provider(db)
    with db.session_scope() as s:
        s.add(ChannelDB(id=f"{PID}_25529", source_id="25529", provider_id=PID,
                        name="LAT| TNT HD", media_type="live"))
        s.add(WatchQueueDB(channel_id=f"{PID}_25529", channel_name="EN - Jeeves And Wooster (1990)",
                           media_type="series", source_id="25529", position=4))
    _refresh(db, [SERIES, LIVE])
    with db.session_scope(commit=False) as s:
        row = s.query(WatchQueueDB).one()
        assert row.channel_id == f"{PID}_series-25529" and row.position == 4
        assert s.get(ChannelDB, row.channel_id).name == "EN - Jeeves And Wooster (1990)"
        assert s.get(ChannelDB, f"{PID}_25529").name == "LAT| TNT HD", "the live row stays live"


def test_the_identity_index_exists_on_a_fresh_and_an_upgraded_database(tmp_path):
    db = Database(f"sqlite:///{tmp_path / 'id.db'}")
    try:
        db.create_tables()

        def has_index():
            with db.engine.connect() as c:
                return bool(c.execute(text("SELECT 1 FROM sqlite_master WHERE name = :n"),
                                      {"n": CHANNEL_IDENTITY_INDEX}).first())
        assert has_index(), "fresh"
        with db.engine.connect() as c:
            c.execute(text(f"DROP INDEX {CHANNEL_IDENTITY_INDEX}"))
            c.commit()
        db._migrate()
        assert has_index(), "an existing database gets it on upgrade"
        from sqlalchemy.exc import IntegrityError
        with db.session_scope() as s:
            s.add(ChannelDB(id="a", source_id="1", provider_id="p", name="x", media_type="live"))
        try:
            with db.session_scope() as s:
                s.add(ChannelDB(id="b", source_id="1", provider_id="p", name="y", media_type="live"))
            raise AssertionError("a second row with the same (source, type, number) was stored")
        except IntegrityError as exc:
            assert "UNIQUE" in str(exc)
    finally:
        db.close()


def test_a_database_that_breaks_the_rule_logs_and_keeps_launching(tmp_path):
    db = Database(f"sqlite:///{tmp_path / 'dup.db'}")
    try:
        db.create_tables()
        with db.engine.connect() as c:
            c.execute(text(f"DROP INDEX {CHANNEL_IDENTITY_INDEX}"))
            c.commit()
        with db.session_scope() as s:
            for cid in ("a", "b"):
                s.add(ChannelDB(id=cid, source_id="1", provider_id="p", name="x", media_type="live"))
        with db.engine.connect() as c:
            assert identity_index_sql(c) == [], "skipped, not a failing CREATE"
        db._migrate()                                   # must not raise
    finally:
        db.close()
