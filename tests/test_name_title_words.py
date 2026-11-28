"""A word before " - " is the title unless it is a code (owner report, 2026-11-28).

"Avatar - Fuoco e cenere [m2160p] [4K] (2025) [ID37849]" was stored as prefix
AVATAR (shown as a language chip), title "Fuoco e cenere [m2160p] [4K] (2025)
[ID37849]". 56 films measured on a large library lost a first word the same way.
"""

from __future__ import annotations

import pytest

from streamselect.core.channel_name_utils import parse_channel_name


@pytest.mark.parametrize("name, title, year, region", [
    ("Avatar - Fuoco e cenere [m2160p] [4K] (2025) [ID37849]", "Avatar - Fuoco e cenere", "2025", ""),
    ("Balan - The Boy (2026)", "Balan - The Boy", "2026", ""),
    ("Robocop - O Polícia do Futuro  (1987)", "Robocop - O Polícia do Futuro", "1987", ""),
    ("Chef - 2017", "Chef", "2017", ""),
    ("KAPI - 2019", "KAPI", "2019", ""),                       # capitals, but only a year follows
    # codes stay prefixes, whatever their case
    ("En - Pretty Woman (1990)", "Pretty Woman", "1990", "EN"),
    ("BR - 1917", "1917", "", "BR"),
    ("IN-EN - Something (2020)", "Something", "2020", "IN-EN"),
    ("MULTI - Title (2019)", "Title", "2019", "MULTI"),
    ("Coupang | Event 10", "Event 10", "", "COUPANG"),           # pipe: packaging, unchanged
])
def test_a_title_word_stays_in_the_title_and_a_code_is_a_prefix(name, title, year, region):
    p = parse_channel_name(name)
    assert (p.bare_name, p.year, p.region) == (title, year, region)


def test_a_provider_id_tag_and_m_marked_quality_leave_the_title():
    p = parse_channel_name("Fuoco e cenere [m2160p] [4K] (2025) [ID37849]")
    assert (p.bare_name, p.year) == ("Fuoco e cenere", "2025") and "4K" in p.quality
