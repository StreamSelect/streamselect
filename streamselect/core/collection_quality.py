"""The quality words at the end of a provider collection name, peeled off and kept.

``channel_name_utils.strip_collection_noise_tokens`` cleans a collection name at
ingestion; its third pass peels a TRAILING run of noise words ("FILMOVI 4K UHD"
-> "FILMOVI"). That pass lives here, because it grew two cases and now returns
what it took (Sports Desk SV-Q68, owner 2026-11-14):

* A run joined by "&" / "+" / "AND": "SPORT HD & HEVC" -> "SPORT", where the old
  pass stopped at the "&" and stored "SPORT HD &".
* Superscript letters ("CROATIA ⱽᴵᴾ ᴿᴬᵂ"): a word is MATCHED in its NFKC fold
  ("RAW"), so it is recognised; what stays in the name is left as written.

The quality words peeled (in name order, each once) are stored at ingestion as
``detected_collection_quality``, so the Sports channel list shows them as chips
and never parses a name at display. Whole-word matching only, never past the
last remaining word — the rules of the pass this replaces.
"""

from __future__ import annotations

import re
import unicodedata

from streamselect.core.quality_vocab import QUALITY_TOKENS

#: Words that join two quality words in a trailing run ("HD & HEVC").
_JOINERS = frozenset({"&", "+", "AND"})
# The last whitespace/hyphen/slash-delimited leaf plus the separators before it.
_TRAILING_LEAF_RE = re.compile(r"[\s\-/]*([^\s\-/]+)\s*$")
_LEAF_SPLIT_RE = re.compile(r"[\s\-/]+")


def _fold(word: str) -> str:
    """The word as matched: superscript and other compatibility forms folded, upper."""
    return unicodedata.normalize("NFKC", word).upper()


def peel_trailing_noise(collection: str, is_noise) -> tuple[str, tuple[str, ...]]:
    """Peel a trailing run of noise words off *collection*.

    Args:
        collection: A collection name with at least one word.
        is_noise: ``channel_name_utils._is_trailing_noise_token`` — the noise
            vocabulary stays defined where it is (one source of truth).

    Returns:
        ``(kept, quality)``: the name with the run removed (never emptier than
        one word), and the quality words that were in the run, folded and in
        name order, each once.
    """
    working = collection
    taken: list[str] = []
    while True:
        leaves = [t for t in _LEAF_SPLIT_RE.split(working.strip()) if t]
        if len(leaves) <= 1:
            break
        last = _fold(leaves[-1])
        if is_noise(last):
            if last in QUALITY_TOKENS and last not in taken:
                taken.insert(0, last)
        elif not (last in _JOINERS and taken):
            break                       # a joiner counts only inside a run already started
        m = _TRAILING_LEAF_RE.search(working)
        working = working[: m.start()].rstrip()
    return working, tuple(taken)


def quality_words(words) -> tuple[str, ...]:
    """The quality words among *words*, folded, in order, each once."""
    return tuple(dict.fromkeys(w for w in map(_fold, words) if w in QUALITY_TOKENS))


def collection_quality_text(quality: tuple[str, ...]) -> str | None:
    """The stored form of the peeled quality words: "HD HEVC", or None for none."""
    return " ".join(quality) or None
