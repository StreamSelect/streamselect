"""One spelling per title, and a bracketed year is the year (reparse v25).

Measured on a large library before the fix (the "yearless movie key" item): the
title-only key was right for 99.4% of the yearless titles a TMDb id could check,
and the wrong merges and splits it did make came from two parser misses, not the
key rule:

* an accented letter sent as a base letter plus a combining mark ("ö" as
  "o" + U+0308): 181 "N. Bölüm" episodes missed the episode marker, and the
  key read the mark as punctuation, so "Véritable" keyed apart from itself;
* a trailing "[1980]" was stripped without its year, so "MOTO GP Assen 500cc
  [1980]" and "[1984]" were one card (27 rows).
"""

from __future__ import annotations

import unicodedata
from types import SimpleNamespace

import pytest

from streamselect.core.channel_name_utils import parse_channel_name
from streamselect.core.content_identity import content_key_for, normalize_title_for_key


def _nfd(s: str) -> str:
    out = unicodedata.normalize("NFD", s)
    assert out != s, "the test name must actually carry a composable accent"
    return out


def _key(name: str) -> str:
    p = parse_channel_name(name)
    return content_key_for(SimpleNamespace(media_type="movie", detected_title=p.bare_name,
                                           detected_year=p.year, detected_tmdb_id=None, id="x"))


def test_a_decomposed_bolum_is_still_the_episode_marker():
    parsed = parse_channel_name(_nfd("Gönül Dağı 215. Bölüm @trt1"))
    assert (parsed.bare_name, parsed.episode) == ("Gönül Dağı", "215")


def test_a_title_keys_the_same_however_its_accents_are_written():
    title = "La Liste de Schindler: la Véritable Histoire"
    assert normalize_title_for_key(_nfd(title)) == normalize_title_for_key(title) \
        == "la liste de schindler la véritable histoire"
    assert _key(f"FR - {_nfd(title)} (2025)") == _key(f"FR - {title} (2025)")


@pytest.mark.parametrize("name, title, year", [
    ("ES - MOTO GP Assen 500cc [1980]", "MOTO GP Assen 500cc", "1980"),
    ("ES - Formula 1 - Abu Dhabi [2021]", "Formula 1 - Abu Dhabi", "2021"),
    ("ES - Real Madrid - Semifinal Champions [2021-2022]", "Real Madrid - Semifinal Champions", "2021-2022"),
])
def test_a_trailing_bracketed_year_is_the_year(name, title, year):
    parsed = parse_channel_name(name)
    assert (parsed.bare_name, parsed.year) == (title, year)


def test_two_years_in_brackets_are_two_cards():
    assert _key("ES - MOTO GP Assen 500cc [1980]") != _key("ES - MOTO GP Assen 500cc  [1984]")


@pytest.mark.parametrize("name", ["EN - Movie [1080]", "NL - Pippi Langkous Serie 1 [1-3]"])
def test_a_bracketed_number_that_is_not_a_year_is_not_read_as_one(name):
    assert parse_channel_name(name).year == ""


def test_the_reparse_runs_again_for_these_fixes():
    from streamselect.core.migrations import detected_title_reparse
    assert detected_title_reparse.CURRENT_VERSION >= 25
