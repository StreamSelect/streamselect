"""Two name-parser rules for words that belong to the TITLE, not its labels.

Read only by ``channel_name_utils.parse_channel_name`` (the one name parser),
kept here because that file is at its size ceiling.

- A provider's own catalogue id ("… (2025) [ID37849]") is cut before anything
  else, and its "m"-marked quality ("[m2160p]") becomes a plain quality token the
  end-anchored quality pass then lifts.
- "Avatar - Fuoco e cenere", "KAPI - 2019": the word before " - " starts the
  title when it is no known code and is written in lower case, or nothing but a
  year follows it (56 films measured on a large library). "En - Pretty Woman",
  "BR - 1917" and the pipe/star packaging forms ("Coupang | Event 10") are left
  as prefixes.
"""

from __future__ import annotations

import re

from streamselect.core.quality_vocab import QUALITY_TOKENS
from streamselect.core.region_codes import PLATFORM_CODES, REGION_FULL_NAMES, normalize_region_code

_PROVIDER_ID_TAG_RE = re.compile(r"\s*\[ID\d+\]\s*$", re.IGNORECASE)
_M_QUALITY_RE = re.compile(r"\s*\[m(\d{3,4}p)\]", re.IGNORECASE)
_YEAR_ONLY_RE = re.compile(r"(19|20)\d\d")


def strip_provider_tags(name: str) -> str:
    """*name* without a trailing ``[IDnnn]`` and with ``[mNNNNp]`` as a bare ``NNNNp``."""
    return _M_QUALITY_RE.sub(r" \1", _PROVIDER_ID_TAG_RE.sub("", name))


def is_dash_title_word(m: "re.Match[str]", bare: str) -> bool:
    """True when the separator match *m* on *bare* is a title word, not a prefix.

    Args:
        m: A ``_SEPARATOR_RE`` match: group 1 the word, group 2 what follows.
        bare: The string it matched.
    """
    between = bare[m.end(1):m.start(2)]
    if "-" not in between or any(c in "|★" for c in between):
        return False
    tok, rest = m.group(1), m.group(2).strip()
    if (normalize_region_code(tok) in REGION_FULL_NAMES or tok.upper() in PLATFORM_CODES
            or tok.upper() in QUALITY_TOKENS):
        return False
    return any(c.islower() for c in tok) or _YEAR_ONLY_RE.fullmatch(rest) is not None
