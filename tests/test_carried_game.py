"""A sports row with no sport of its own shows the sport of the game it carries.

One Sports List slice 3 (OL-Q13): read through ``game_feeds`` when a page of
rows is built, never stored on the channel. Real file database; the painted
row is read through the delegate's own paint().
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from PyQt6.QtCore import QRect

from streamselect.core import sports_catalog as sc
from streamselect.core.database import ChannelDB, ProviderDB
from streamselect.core.games.carried import CarriedGame, carried_games
from streamselect.core.games.models import GameDB, GameFeedDB
from streamselect.core.repositories import RepositoryFactory
from streamselect.core.repositories.channel_list_rows import rows_to_dtos
from streamselect.core.repositories.dtos import ChannelListDTO

NOW = datetime(2026, 11, 27, 20, 0)


def _game(s, channel_id, start, *, sport="hockey", league="NHL", a="Calgary Flames",
          b="Edmonton Oilers", level=1):
    g = GameDB(sport=sport, league=league, team_a=a, team_b=b, start_utc=start, level=level,
               replay=False, collections=2, found_at=NOW)
    g.feeds = [GameFeedDB(channel_id=channel_id, source="p1", collection="C", name="n")]
    s.add(g)


def test_the_game_on_now_wins_over_an_earlier_one_and_a_later_one(db):
    with db.session_scope() as s:
        _game(s, "slot1", NOW - timedelta(hours=9), a="Old A", b="Old B")       # long over
        _game(s, "slot1", NOW - timedelta(minutes=30))                          # on now
        _game(s, "slot1", NOW + timedelta(minutes=90), a="Later A", b="Later B")
    with db.session_scope(commit=False) as s:
        got = carried_games(s, ["slot1"], NOW)
    assert got["slot1"].title == "Calgary Flames vs Edmonton Oilers"
    assert (got["slot1"].sport, got["slot1"].league) == ("hockey", "NHL")


def test_nothing_on_now_takes_the_next_game_and_a_doubtful_game_is_never_read(db):
    with db.session_scope() as s:
        _game(s, "slot2", NOW + timedelta(minutes=60), sport="basketball", league="NBA",
              a="Miami Heat", b="New York Knicks")
        _game(s, "slot3", NOW - timedelta(minutes=10), level=3)                 # not listed
    with db.session_scope(commit=False) as s:
        got = carried_games(s, ["slot2", "slot3", "nobody"], NOW)
    assert set(got) == {"slot2"}
    assert got["slot2"].sport == "basketball"


def test_only_rows_stored_as_a_kind_are_given_the_game(db):
    with db.session_scope() as s:
        s.add(ProviderDB(id="p1", name="One", type="xtream", url="http://example.com",
                         username="u", password="p", is_active=True))
        for cid, kind in (("slot1", sc.SLOT), ("net1", sc.NETWORK), ("nhl1", "hockey")):
            s.add(ChannelDB(id=cid, source_id=cid, provider_id="p1", name=cid,
                            media_type="live", sport_type=kind))
            _game(s, cid, NOW - timedelta(minutes=5))
    with db.session_scope(commit=False) as s:
        rows = s.query(ChannelDB).order_by(ChannelDB.id).all()
        from unittest.mock import patch
        with patch("streamselect.core.repositories.channel_list_rows.now_utc", lambda: NOW):
            dtos = {d.id: d for d in rows_to_dtos(RepositoryFactory(s), rows, None)}
    assert dtos["slot1"].carried_game.sport == "hockey"
    assert dtos["net1"].carried_game.sport == "hockey"
    assert dtos["nhl1"].carried_game is None, "a row naming its own sport is left as it is"


def _live_slot_dto(carried) -> ChannelListDTO:
    return ChannelListDTO(id=str(uuid.uuid4()), name="US: SOCCER PPV 80", media_type="live",
                          provider_id="p1", is_favorite=False, category="PPV", quality=None,
                          detected_prefix=None, detected_region=None, detected_quality=None,
                          detected_year=None, detected_title="SOCCER PPV 80", user_rating=0,
                          sport_type=sc.SLOT, carried_game=carried)


def _painted(qapp, dto):
    from streamselect.gui.channel_list_delegate import ChannelRowDelegate
    from streamselect.gui.channel_list_model import ChannelListModel
    from tests.conftest import paint_channel_row

    model = ChannelListModel()
    model.set_channels([dto], provider_icon_map={}, show_provider_icon=False, has_more=False,
                       query_params={}, get_media_type_icon=lambda mt: "")
    return {c.text: c for _r, c in paint_channel_row(ChannelRowDelegate(), model.index(0),
                                                    rect=QRect(0, 0, 900, 68)).cells}


def test_the_row_paints_the_games_sport_and_league_and_the_tooltip_says_why(qapp):
    game = CarriedGame("hockey", "NHL", "Calgary Flames vs Edmonton Oilers", NOW)
    cells = _painted(qapp, _live_slot_dto(game))
    assert "Hockey" in cells and "Event slot" not in cells
    assert "NHL" in cells
    tip = cells["Hockey"].tip
    assert "Calgary Flames vs Edmonton Oilers" in tip and "Event slot" in tip


def test_a_slot_carrying_nothing_still_reads_event_slot(qapp):
    cells = _painted(qapp, _live_slot_dto(None))
    assert "Event slot" in cells and "Hockey" not in cells
