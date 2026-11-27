"""The one sports list (core/sports_catalog.py, design "One Sports List").

Every case here is a row shape measured on a real library on 2026-11-27, with
the names made neutral. Each asserts the stored outcome that broke before.
"""

import pytest

from streamselect.core import sports_catalog as sc
from streamselect.core.database import ChannelDB
from streamselect.core.special_content import parse_sports_channel, update_channel_special_content


def _tag(name, category=""):
    t = parse_sports_channel(ChannelDB(id="x", name=name, category=category, media_type="live"))
    return t["sport_type"], t["league_name"], t["sport_from"]


def test_a_league_word_names_its_sport():
    assert _tag("US| NHL CENTER ICE 3") == ("hockey", "NHL", sc.FROM_LEAGUE)


def test_a_league_of_another_sport_is_never_stored_under_this_one():
    # Was league UFC under sport boxing (20 rows): the name says boxing, the
    # collection says UFC.
    assert _tag("Boxing  05  :  Canelo vs Mbilli UK 2:00pm", "UK| UFC PPV") == ("boxing", None, sc.FROM_WORD)


def test_a_league_name_beats_a_sport_word():
    # "football" is soccer's word; "Football: NFL …" is American football.
    assert _tag("US (ESPN+ 188) | Football: NFL Gameday Final (2026-11-27 18:01:00)")[:2] == (
        "american_football", "NFL")
    # And the Oakland Athletics play baseball.
    assert _tag("US| MLB OAKLAND ATHLETICS HD")[:2] == ("baseball", "MLB")


def test_the_longer_sport_word_wins():
    assert _tag("NCAA Football: Tulsa vs. UTSA")[0] == "american_football"
    assert _tag("EN| FIELD HOCKEY WORLD LEAGUE")[0] == "field_hockey"


def test_the_name_beats_the_collection():
    # A collection named after one sport carries others.
    assert _tag("Next | Steelers Vs Broncos || English | NFL | 27-11-2026 | 19:40 (GMT)",
                "AR| FOOTBALL PPV")[:2] == ("american_football", "NFL")
    # With nothing in the name, the collection decides.
    assert _tag("AR| MATCH 4 HD", "AR| FOOTBALL PPV")[0] == "soccer"


def test_a_slot_label_is_not_the_event():
    # "SOCCER PPV 80" is the slot's own name; it carried an NFL special.
    assert _tag("End | NFL Thanksgiving Special | all | 27-11-2026 | 18:42 (GMT) | US: SOCCER PPV 24")[:2] == (
        "american_football", "NFL")


def test_a_slot_label_alone_is_a_labelled_guess():
    assert _tag("Next | Ferencvaros vs. Celje | all | 26-11-2026 | 20:44 (GMT) | US: SOCCER PPV 80") == (
        "soccer", None, sc.FROM_LABEL)


def test_a_shared_league_name_is_a_guess():
    assert _tag("|AU| Optus Sport 4 (EPL Match Only)") == ("soccer", "Premier League", sc.FROM_LEAGUE_GUESS)
    # A sport word on the listing decides instead.
    assert _tag("IN| CRICKET: Indian Premier League")[0] == "cricket"


@pytest.mark.parametrize("name, category", [
    ("|UK| SKY SPORTS ACTION HD", ""),
    ("AR| BEIN SPORTS 8 HD", ""),
    ("US| MSG 2 HD", "US| SPORTS NETWORK"),
])
def test_a_channel_carrying_many_sports_is_a_network(name, category):
    assert _tag(name, category) == (sc.NETWORK, None, None)


@pytest.mark.parametrize("name", [
    "- NO EVENT STREAMING - | 8K | US: ESPN+ PPV 896",
    "TNT SPORTS | Event 12",
    "|ESPN+ 55 : ",
    "CA (SN+ 049) |  (2098-12-31 08:00:24)",
])
def test_an_event_slot_with_nothing_naming_its_sport_is_a_slot(name):
    assert _tag(name)[0] == sc.SLOT


def test_a_game_nothing_identified_is_unknown_not_a_network():
    assert _tag("US| SPORTS 7 | Motor Lublin vs Lech Poznan (2026-12-05 11:25:00)")[0] == sc.UNKNOWN


def test_a_new_word_tags_what_it_names():
    # flohoops: about 190 basketball games stored "unknown" before.
    assert _tag("flohoops: 2026 Pacific vs Omaha - Men's (2026-11-26 22:30:00)", "US| FLO NETWORK")[0] == "basketball"


def test_a_word_written_as_a_stem_and_a_league_credits_both():
    # "f1*" (Racing's stem) and "F1" (the Formula 1 league) spell the same
    # token; 127 rows lost their league when the stem shadowed it.
    assert _tag("|VIA |VIAPLAY F1 2: ")[:2] == ("racing", "Formula 1")
    assert _tag("|F1| F1TV PRO")[0] == "racing"


def test_ppv_rows_read_the_same_list():
    ch = ChannelDB(id="p", name="End | Buffalo Bills Vs Kansas City Chiefs | all | 27-11-2026 | 01:29 (GMT) | PPV",
                   category="", media_type="live", stream_url="http://example.com/1")
    assert update_channel_special_content(ch) is True
    assert ch.special_view == "ppv"
    # The PPV map wrote "football" for American football, a key nothing knew.
    assert (ch.sport_type, ch.sport_from) == ("american_football", sc.FROM_WORD) or ch.sport_type == sc.UNKNOWN
    assert ch.sport_type != "football"


def test_the_finder_runs_only_listed_and_trial_leagues():
    names = {(lg.sport, lg.name) for lg in sc.finder_leagues()}
    assert ("hockey", "NHL") in names and ("basketball", "NBA") in names
    assert ("hockey", "OHL") not in names          # tagging only
    assert all(lg.finder in (sc.FINDER_LISTED, sc.FINDER_TRIAL) for lg in sc.finder_leagues())


def test_the_sports_view_order_is_unchanged():
    from streamselect.core.games.store import sport_settings
    assert list(sport_settings())[:2] == ["hockey", "basketball"]


def test_every_league_word_is_found_only_under_one_sport_unless_shared():
    seen = {}
    for s in sc.sports():
        for lg in s.leagues:
            for w in lg.words:
                key = w.lower()
                if key in seen and not lg.shared:
                    assert seen[key] == s.key, f"{w!r} is a league word of {seen[key]} and {s.key}"
                seen.setdefault(key, s.key)


def test_a_stored_kind_reads_as_words():
    assert sc.sport_label("american_football") == "American football"
    assert sc.sport_label(sc.NETWORK) == "Many sports"
    assert sc.sport_label(sc.SLOT) == "Event slot"
    assert sc.sport_label("") == ""


def test_the_row_chip_names_a_kind_in_words():
    """The sport chip paints the list's name for a stored value, never the raw key."""
    from streamselect.gui.channel_row_cells import _sport_cell

    assert _sport_cell(sc.NETWORK).text == "Many sports"
    assert _sport_cell(sc.SLOT).text == "Event slot"
    assert _sport_cell("american_football").text == "American football"
