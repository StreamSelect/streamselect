"""The game finder: listings in several formats become one game, at the right start.

Collection names here are neutral labels; team names are public league teams.
Times are UTC-naive throughout, as the finder stores them.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from streamselect.core.database import ChannelDB, EpgProgramDB, ProviderDB
from streamselect.core.games.finder import GUIDE, ListingIn, Memory, SportSettings, find_games
from streamselect.core.games.models import GameDB, GameFeedDB, GameFinderMemoryDB
from streamselect.core.games.store import refresh_games

NOW = datetime(2026, 11, 13, 3, 12)
NHL = SportSettings("hockey", "NHL", ("NHL",))
START = datetime(2026, 11, 13, 1, 5)     # 8:05 PM US Eastern, 02:05 CET


def _two_games() -> list[ListingIn]:
    """Two games at 01:05 UTC, each listed four ways plus one guide programme."""
    return [
        # Zone stated, with a date: anchors.
        ListingIn("p1", "COLL ZONE A", "LIVE | NHL: CHICAGO BLACKHAWKS - BUFFALO SABRES | Fri 13 Nov 02:05 CET | PPV 4", "a1"),
        ListingIn("p1", "COLL ZONE A", "LIVE | NHL: WINNIPEG JETS - DALLAS STARS | Fri 13 Nov 02:05 CET | PPV 5", "a2"),
        ListingIn("p1", "COLL ZONE B", "LIVE | BUFFALO SABRES VS. CHICAGO BLACKHAWKS | Thu 12 Nov 8:05 PM ET", "b1"),
        ListingIn("p1", "COLL ZONE B", "LIVE | WINNIPEG JETS VS. DALLAS STARS | Thu 12 Nov 8:05 PM ET", "b2"),
        # A date but no zone: this collection runs two hours ahead of UTC, learned from the anchors.
        ListingIn("p2", "COLL CLOCK", "NHL: Chicago Blackhawks vs Buffalo Sabres @ Nov 13 03:05 :Play 14", "c1"),
        ListingIn("p2", "COLL CLOCK", "NHL: Dallas Stars vs Winnipeg Jets @ Nov 13 03:05 :Play 15", "c2"),
        # No zone and no date, short names glued to a slot number: an Eastern clock, learned.
        ListingIn("p2", "COLL SLOTS", "NHL | 08 - 8pm Sabres @ Blackhawks", "s1"),
        ListingIn("p2", "COLL SLOTS", "NHL | 09 - 8pm Jets @ Stars", "s2"),
        ListingIn(GUIDE, "Guide channel 1", "NHL: Chicago Blackhawks - Buffalo Sabres", "g1", START),
    ]


def _game(games, team):
    hits = [g for g in games if team in (g.team_a, g.team_b)]
    assert len(hits) == 1, [g.title for g in games]
    return hits[0]


def test_every_format_of_one_game_joins_one_game_at_its_real_start():
    games, _, clocks = find_games(_two_games(), NHL, NOW)
    g = _game(games, "Buffalo Sabres")
    assert g.title == "Buffalo Sabres vs Chicago Blackhawks"
    assert g.start_utc == START
    assert g.level == 1 and not g.replay
    assert {f.channel_id for f in g.feeds} == {"a1", "b1", "c1", "s1", "g1"}
    # The guide counts once; four channel collections + the guide = five.
    assert g.collections == 5
    by_id = {f.channel_id: f for f in g.feeds}
    assert by_id["c1"].time_from == "clock" and by_id["c1"].start_utc == START
    assert by_id["s1"].time_from == "clock" and abs(by_id["s1"].start_utc - START) <= timedelta(minutes=5)
    assert by_id["g1"].from_guide and by_id["g1"].counts
    learned = {c.collection: c.offset_min for c in clocks if c.learned}
    assert learned == {"COLL CLOCK": 120, "COLL SLOTS": -300}


def test_one_collection_is_level_2_and_a_rematch_of_a_confirmed_game_is_a_replay():
    one = [ListingIn("p1", "COLL ZONE A", "NHL: Boston Bruins vs Montreal Canadiens | Fri 13 Nov 01:00 CET", "x1")]
    games, _, _ = find_games(_two_games() + one, NHL, NOW)
    assert _game(games, "Boston Bruins").level == 2

    earlier = Memory(confirmed={"Boston Bruins vs Montreal Canadiens": {datetime(2026, 11, 12, 0, 0)}})
    games, _, _ = find_games(_two_games() + one, NHL, NOW, earlier)
    g = _game(games, "Boston Bruins")
    assert (g.level, g.replay) == (3, True)


def test_the_guide_alone_never_makes_a_confirmed_game():
    """Two guide channels naming one game are one input, not two agreeing collections."""
    t = datetime(2026, 11, 13, 2, 0)
    guide_only = [ListingIn(GUIDE, "Guide channel 1", "NHL: St. Louis Blues - Utah Mammoth", "g4", t),
                  ListingIn(GUIDE, "Guide channel 2", "NHL: Utah Mammoth - St. Louis Blues", "g5", t)]
    games, _, _ = find_games(_two_games() + guide_only, NHL, NOW)
    g = _game(games, "Utah Mammoth")
    assert (g.collections, g.level) == (1, 2)
    assert all(f.from_guide for f in g.feeds)


def test_another_sport_sharing_a_city_never_joins():
    others = [ListingIn("p1", "COLL FOOTBALL", "Florida State vs Boston College 8:00 PM ET", "f1"),
              ListingIn("p1", "COLL ZONE A", "NHL: Boston Bruins vs Florida Panthers | Fri 13 Nov 02:00 CET", "h1")]
    games, _, _ = find_games(_two_games() + others, NHL, NOW)
    assert all(f.channel_id != "f1" for g in games for f in g.feeds)


def test_a_teamless_guide_programme_is_a_feed_only_when_one_game_starts_close_by():
    teamless = ListingIn(GUIDE, "Guide channel 2", "Live: NHL Hockey", "g2", START)
    games, _, _ = find_games(_two_games() + [teamless], NHL, NOW)
    # Two games start at 01:05: which one the programme shows is unknown, so it joins neither.
    assert all(f.channel_id != "g2" for g in games for f in g.feeds)

    lone = [ListingIn("p1", "COLL ZONE A", "NHL: Los Angeles Kings vs New York Islanders | Fri 13 Nov 04:05 CET", "k1"),
            ListingIn("p1", "COLL ZONE B", "NEW YORK ISLANDERS VS. LOS ANGELES KINGS | Thu 12 Nov 10:05 PM ET", "k2"),
            ListingIn(GUIDE, "Guide channel 2", "Live: NHL Hockey", "g3", datetime(2026, 11, 13, 3, 0))]
    games, _, _ = find_games(_two_games() + lone, NHL, NOW)
    g = _game(games, "Los Angeles Kings")
    feed = [f for f in g.feeds if f.channel_id == "g3"]
    assert len(feed) == 1 and feed[0].from_guide and not feed[0].counts
    assert g.collections == 2          # it added a feed, not evidence


def test_a_dateless_name_unchanged_for_two_days_is_stale():
    stale = ListingIn("p1", "COLL ZONE A", "NHL: Nashville Predators @ Colorado Avalanche 9:30pm ET", "st")
    games, mem, _ = find_games(_two_games() + [stale], NHL, NOW)
    assert any("Nashville Predators" in g.title for g in games)
    assert mem.first_seen[("st", stale.name)] == NOW

    old = Memory(first_seen={("st", stale.name): NOW - timedelta(hours=49)})
    games, _, _ = find_games(_two_games() + [stale], NHL, NOW, old)
    assert not any("Nashville Predators" in g.title for g in games)


def _seed_db(db) -> None:
    with db.session_scope() as s:
        s.add(ProviderDB(id="p1", name="One", type="xtream", url="http://example.com", username="u",
                         password="p", is_active=True))
        s.add(ProviderDB(id="p2", name="Two", type="xtream", url="http://example.com", username="u",
                         password="p", is_active=True))
        s.add(ProviderDB(id="off", name="Off", type="xtream", url="http://example.com", username="u",
                         password="p", is_active=False))
        for li in _two_games():
            if li.source == GUIDE:
                s.add(EpgProgramDB(provider_id="p1", channel_epg_id="g1", channel_db_id="a1",
                                   channel_name=li.collection, title=li.name, start_time=li.guide_utc,
                                   stop_time=li.guide_utc + timedelta(hours=3)))
            else:
                s.add(ChannelDB(id=li.channel_id, source_id=li.channel_id, provider_id=li.source,
                                name=li.name, category=li.collection, media_type="live"))
        # A switched-off source's listing must never count.
        s.add(ChannelDB(id="o1", source_id="o1", provider_id="off", name="NHL: Buffalo Sabres vs Chicago "
                        "Blackhawks | Fri 13 Nov 02:05 CET", category="COLL OFF", media_type="live"))


def test_refresh_games_stores_games_and_replaces_them_on_the_next_run(db):
    _seed_db(db)
    counts = refresh_games(db, NOW)
    assert counts["hockey/NHL"] == 2
    assert all(n == 0 for k, n in counts.items() if k != "hockey/NHL"), "no other league's games here"
    refresh_games(db, NOW + timedelta(minutes=5))
    with db.session_scope(commit=False) as s:
        games = s.query(GameDB).order_by(GameDB.team_a).all()
        assert [(g.team_a, g.team_b, g.level, g.start_utc) for g in games] == [
            ("Buffalo Sabres", "Chicago Blackhawks", 1, START),
            ("Dallas Stars", "Winnipeg Jets", 1, START)]
        feeds = {f.channel_id for f in s.query(GameFeedDB).filter(GameFeedDB.game_id == games[0].id)}
        assert feeds == {"a1", "b1", "c1", "s1"} | {"a1"}  # the guide programme is linked to channel a1
        assert s.query(GameFeedDB).count() == 9           # replaced, not appended
        memory = s.get(GameFinderMemoryDB, "hockey/NHL").memory
        assert any(src == "p2" and coll == "COLL CLOCK" for src, coll, *_ in memory["clock_samples"])


def test_a_listing_that_says_at_or_at_sign_names_the_home_team():
    """Owner, 2026-11-14: "if we have an AT or @ we should use AT rather than VS"."""
    games, _, _ = find_games(_two_games(), NHL, NOW)
    assert _game(games, "Buffalo Sabres").home == "Chicago Blackhawks"      # "Sabres @ Blackhawks"
    assert _game(games, "Dallas Stars").home == "Dallas Stars"               # "Jets @ Stars"
    worded = [ListingIn(li.source, li.collection, li.name.replace("Jets @ Stars", "Jets at Stars"),
                        li.channel_id, li.guide_utc) for li in _two_games()]
    games, _, _ = find_games(worded, NHL, NOW)
    assert _game(games, "Dallas Stars").home == "Dallas Stars", "the word works like the sign"


def test_listings_that_disagree_about_home_name_no_home_team():
    listings = _two_games() + [
        ListingIn("p3", "COLL OTHER", "NHL | 07 - 8pm Blackhawks @ Sabres", "o1")]
    games, _, _ = find_games(listings, NHL, NOW)
    assert _game(games, "Buffalo Sabres").home == ""


def test_names_fold_to_one_spelling_with_or_without_accents():
    """The plain-ASCII shortcut must agree with the full fold (measured identical
    on 128,936 real names, 2026-11-17)."""
    from streamselect.core.games.listing_text import norm
    assert norm("Montréal Canadiens") == norm("MONTREAL CANADIENS") == "MONTREAL CANADIENS"
    assert norm("ＮＨＬ ｖｓ") == "NHL VS", "full-width letters still recompose"
    assert norm("Boston Bruins vs") == "BOSTON BRUINS VS"
    assert norm(None) == norm("") == ""


def test_the_read_leaves_out_only_channels_that_cannot_name_a_game(db):
    """The finder's read is narrowed in SQL (2026-11-17): a channel with no league
    word and no matchup stays in the database, and the games found are the same
    as reading every live channel."""
    from unittest import mock

    from streamselect.core.games import store
    _seed_db(db)
    with db.session_scope() as s:
        for cid, name, coll in [
            ("n1", "US: ESPN News", "SPORTS"),                          # nothing to read
            ("n2", "Bruins vs Canadiens 7PM", "ZONE"),                  # a matchup: kept
            ("n3", "ＮＨＬ Network", "ZONE"),                            # full-width: kept
            ("n4", "Hockey Night", "CA| ᴿᴬᵂ SPORTS"),                    # decorated, no league word
            ("n5", "Hockey Night", "CA| ᴺᴴᴸ ᴾᴬᶜᴷ"),                      # superscript NHL folds to NHL
        ]:
            s.add(ChannelDB(id=cid, source_id=cid, provider_id="p1", name=name, category=coll,
                            media_type="live"))
    with db.session_scope(commit=False) as s:
        narrowed = {li.channel_id for li in store._read_listings(s, NHL, NOW, set())}
        with mock.patch.object(store, "_could_name_a_game", lambda *_: None):
            everything = {li.channel_id for li in store._read_listings(s, NHL, NOW, set())}
    assert "n1" in everything and "n1" not in narrowed
    assert "n4" not in narrowed, "a category that does not name the league after folding"
    assert {"n2", "n3", "n5"} <= narrowed
    dropped = everything - narrowed
    assert dropped == {"n1", "n4"}, dropped
    first = refresh_games(db, NOW)
    with mock.patch.object(store, "_could_name_a_game", lambda *_: None):
        assert refresh_games(db, NOW) == first


# ── Borrowed clocks (owner, 2026-11-17: no timing typed in; figure it out) ──

def _ahl():
    from streamselect.core.games.finder import SportSettings
    return SportSettings("hockey", "AHL", ("AHL",))


def _clock(coll, off, src="p2"):
    from streamselect.core.games.finder import Clock
    return Clock(src, coll, off, 10, 10)


_SIBLINGS = (_clock("CA| SPORTS PPV", -300), _clock("US| NHL GAMES", -300))


def _calgary(flo_time="20:00:00", ppv_coll="CA| AHL PPV", flo_coll="US| STREAM NETWORK"):
    return [ListingIn("p2", ppv_coll, "AHL 03 : 8pm Calgary Wranglers vs Coachella Valley Firebirds", "x1"),
            ListingIn("p2", flo_coll, "streamhockey: 2026 Calgary Wranglers vs Coachella Valley Firebirds "
                                      f"(2026-11-12 {flo_time})", "x2")]


def test_a_collection_with_no_clock_borrows_its_siblings_and_the_game_is_placed():
    games, _, clocks = find_games(_calgary(), _ahl(), NOW, None, _SIBLINGS)
    g = _game(games, "Calgary Wranglers")
    assert g.start_utc == datetime(2026, 11, 13, 1, 0), "8pm on the siblings' -5 h clock"
    assert g.level == 1, "two collections, and their borrowed times agree"
    assert {f.time_from for f in g.feeds} == {"borrowed"}
    lent = {c.collection: c.borrowed_from for c in clocks if c.borrowed_from}
    assert lent == {"CA| AHL PPV": "CA| SPORTS PPV", "US| STREAM NETWORK": "US| NHL GAMES"}


def test_borrowed_times_that_disagree_leave_the_game_less_certain():
    """Cleveland at Hamilton on 2026-11-17: "8pm" in one, 19:00 in the other."""
    games, _, _ = find_games(_calgary(flo_time="19:00:00"), _ahl(), NOW, None, _SIBLINGS)
    assert _game(games, "Calgary Wranglers").level == 2


def test_siblings_that_disagree_lend_nothing_and_nothing_is_guessed():
    split = (_clock("CA| SPORTS PPV", -300), _clock("CA| OTHER PPV", -360), _clock("US| NHL GAMES", -300))
    games, _, clocks = find_games(_calgary(), _ahl(), NOW, None, split)
    assert "CA| AHL PPV" not in {c.collection for c in clocks if c.borrowed_from}
    # The AHL listing has no time, and the FLO listing alone (no league word) is
    # not a seed: no game is made from a guess.
    assert games == []


def test_a_collection_without_a_region_borrows_nothing():
    games, _, clocks = find_games(_calgary(ppv_coll="AHL PPV", flo_coll="STREAM NETWORK"),
                                  _ahl(), NOW, None, _SIBLINGS)
    assert not [c for c in clocks if c.borrowed_from] and games == []


def test_the_same_collections_own_clock_from_another_league_beats_its_siblings():
    known = _SIBLINGS + (_clock("CA| AHL PPV", -360),)
    _games, _, clocks = find_games(_calgary(), _ahl(), NOW, None, known)
    mine = next(c for c in clocks if c.collection == "CA| AHL PPV")
    assert mine.offset_min == -360 and mine.borrowed_from == "CA| AHL PPV"


def test_a_refresh_lends_one_leagues_learned_clocks_to_another(db):
    """The NHL run learned "CA| SPORTS PPV"'s clock; the AHL run, whose collection
    never showed one, places its games with it — through the stored memory."""
    from streamselect.core.games.models import GameFinderMemoryDB
    with db.session_scope() as s:
        s.add(ProviderDB(id="p2", name="Two", type="xtream", url="http://example.com", username="u",
                         password="p", is_active=True))
        seen = NOW.isoformat()
        s.add(GameFinderMemoryDB(finder="hockey/NHL", updated_at=NOW, memory={
            "clock_samples": [["p2", "CA| SPORTS PPV", "A vs B@1", -300, seen],
                              ["p2", "CA| SPORTS PPV", "C vs D@2", -300, seen],
                              ["p2", "US| NHL GAMES", "A vs B@1", -300, seen],
                              ["p2", "US| NHL GAMES", "C vs D@2", -300, seen]],
            "first_seen": [], "confirmed": {}}))
        for li in _calgary():
            s.add(ChannelDB(id=li.channel_id, source_id=li.channel_id, provider_id=li.source,
                            name=li.name, category=li.collection, media_type="live"))
    counts = refresh_games(db, NOW)
    assert counts["hockey/AHL"] == 1
    with db.session_scope(commit=False) as s:
        g = s.query(GameDB).filter(GameDB.league == "AHL").one()
        assert g.start_utc == datetime(2026, 11, 13, 1, 0)
