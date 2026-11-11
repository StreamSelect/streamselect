"""Continent headings in provider categories — found by counting, never listed.

Some sources file their live lineup one level above the country:
``"AM| CANADA HD"``, ``"AM| BRAZIL"``, ``"AM| AUSTRALIA"``. ``AM`` there is the
Americas folder, but read as a code it is Armenia, so every row under it was
stored Armenian. A hand-kept list of such headings would only know the ones
somebody noticed, so the parser asks the source instead:

* **Per source:** a category head with at least :data:`HEADING_MIN_COUNTRIES`
  different countries filed under it is a heading for that source. Measured on
  two sources: headings carry 4-17 countries (``AM`` 17, ``ARAB``/``EU`` 15,
  ``ASIA`` 13, ``LAT`` 11, ``AF`` 8), a real country carries 1 (itself), and
  nothing sat at 3.
* **Per category:** a head followed by a DIFFERENT country's name is a heading
  for that category (``"SK| SOUTH KOREA"`` is not Slovakia) — no source needed.

A heading only loses a COUNTRY reading. ``AF`` (Africa), ``LAT`` (Latin
America) and ``AR`` (Arabic) still mean what they say for the whole folder, so
they keep their tags; ``AM`` loses Armenia. The country under the heading (or
the channel's own prefix) decides the region.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from streamselect.core.region_codes import (
    REGION_FULL_NAMES,
    is_country_code,
    leading_country,
    normalize_region_code,
)

#: Different countries a head must cover in one source to count as a heading.
HEADING_MIN_COUNTRIES: int = 3


def split_head(category: str | None) -> tuple[str, str]:
    """``("AM", "CANADA HD")`` for ``"AM| CANADA HD"``; ``("", "")`` with no pipe.

    A leading pipe (``"|NA| …"``) is accepted. A head containing a space is not
    a code (``"ASIA | 24/7 INDIA"`` → ``"ASIA"`` is kept; ``"US SPORTS| …"`` is not).
    """
    head, sep, rest = (category or "").strip().lstrip("|").partition("|")
    head = head.strip().upper()
    if not sep or not head or " " in head:
        return "", ""
    return head, rest.strip()


def _country_name(code: str) -> str:
    """Display name for *code*, so ``DE`` and ``GER`` compare equal."""
    code = normalize_region_code(code)
    return REGION_FULL_NAMES.get(code, code)


def detect_headings(categories: Iterable[str | None]) -> frozenset[str]:
    """Heads that file at least :data:`HEADING_MIN_COUNTRIES` countries under them.

    Args:
        categories: One source's distinct category labels.

    Returns:
        The heads that are headings for that source.
    """
    under: dict[str, set[str]] = defaultdict(set)
    for category in categories:
        head, rest = split_head(category)
        country = leading_country(rest) if head else None
        if country:
            under[head].add(_country_name(country[0]))
    return frozenset(h for h, names in under.items() if len(names) >= HEADING_MIN_COUNTRIES)


def masks_country(category: str | None, headings: frozenset[str] = frozenset()) -> bool:
    """True when *category*'s head is a country code used here as a heading.

    Args:
        category: A provider category label.
        headings: The source's headings from :func:`detect_headings`.

    Returns:
        True for ``"AM| CANADA HD"`` (a different country follows) and for
        ``"AM| CARIBBEAN"`` when ``AM`` is in *headings*; False for
        ``"AM| ARMENIA"``, ``"DE| GERMANY"`` and for non-country heads such as
        ``"AF| ZIMBABWE"``.
    """
    head, rest = split_head(category)
    if not head or not is_country_code(head):
        return False
    if head in headings:
        return True
    country = leading_country(rest)
    return bool(country) and _country_name(country[0]) != _country_name(head)


def headings_by_provider(session, provider_id: str | None = None) -> dict[str, frozenset[str]]:
    """``{provider_id: headings}`` from one query over distinct categories.

    Args:
        session: An open SQLAlchemy session.
        provider_id: Limit to one source, or None for all.

    Returns:
        Each source's headings; a source with none maps to an empty set.
    """
    from streamselect.core.database import ChannelDB

    query = session.query(ChannelDB.provider_id, ChannelDB.category).distinct()
    if provider_id:
        query = query.filter(ChannelDB.provider_id == provider_id)
    by_provider: dict[str, list[str]] = defaultdict(list)
    for pid, category in query.all():
        by_provider[pid].append(category)
    return {pid: detect_headings(cats) for pid, cats in by_provider.items()}
