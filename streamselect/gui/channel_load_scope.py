"""Which sources a channel-list load covers, resolved off the UI thread.

``load_channels`` used to read every source on the UI thread before handing
the query to a worker ("tiny queries"). At launch that read opened a database
connection while several background threads were opening theirs, and the
window froze for 1.3 s waiting (watchdog, 2026-11-17). The read now runs at
the start of the worker, and :func:`provider_scope` turns its rows into the
keys ``_query_channels`` and the result handler read.
"""

from __future__ import annotations

from typing import Iterable, NamedTuple, Optional


class SourceRow(NamedTuple):
    """The four facts about a source a channel load needs."""

    id: str
    active: bool
    force_adult: bool
    icon: str


def provider_scope(sources: Iterable[SourceRow], *, given_provider_id: Optional[str],
                   excluded_ids: set, default_icon: str) -> dict:
    """The provider keys of a channel-load ``params`` dict.

    Args:
        sources: every configured source.
        given_provider_id: the one source the caller asked for, if any.
        excluded_ids: sources the filter panel unticked.
        default_icon: the badge for a source without its own icon.

    Returns:
        ``provider_id`` (one id, a list of ids, or None for all),
        ``force_adult_ids``, ``show_provider_icon``, ``provider_icon_map`` and
        ``has_any_provider``.
    """
    sources = list(sources)
    active_ids = [s.id for s in sources if s.active]
    if given_provider_id:
        target = given_provider_id
    else:
        visible = [pid for pid in active_ids if pid not in excluded_ids]
        if len(visible) == len(active_ids) == 1:
            target = visible[0]
        elif len(visible) < len(active_ids):
            target = visible or None
        else:
            target = None
    show_icon = target is None
    return {
        "provider_id": target,
        "force_adult_ids": [s.id for s in sources if s.force_adult],
        "show_provider_icon": show_icon,
        "provider_icon_map": {s.id: s.icon or default_icon for s in sources} if show_icon else {},
        "has_any_provider": bool(sources),
    }


def with_provider_scope(repos, params: dict, *, excluded_ids: set, default_icon: str) -> dict:
    """Worker side: read the sources and return *params* with their keys filled.

    A new dict, so the one the UI thread built is never written from a worker.
    """
    sources = [SourceRow(p.id, bool(p.is_active), bool(getattr(p, "force_adult", False)),
                         getattr(p, "icon", "") or "")
               for p in repos.providers.get_all()]
    return {**params, **provider_scope(sources, given_provider_id=params.get("given_provider_id"),
                                       excluded_ids=excluded_ids, default_icon=default_icon)}
