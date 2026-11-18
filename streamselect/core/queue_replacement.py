"""Swap Watch Queue items on unusable sources for the same title on an active one.

A queued item keeps pointing at the copy it was queued from. When that source
expires or is switched off, the item cannot play, though the same title is
often on a source that still works. The Watch Queue's "Replace unavailable
items…" window lists those items with a proposed copy, and :func:`replace`
swaps the ticked ones (owner, 2026-11-17):

- the item keeps its place in the queue and its date added;
- the old copy's watch history moves to the new copy;
- items with no copy are listed and left alone;
- :func:`undo` puts everything back, from the snapshot :func:`replace` returns.

Copies come from ``channel_live_copy.live_siblings`` — the one rule the details
pane also uses (same ``content_key`` and media type, usable sources only). This
window adds one preference on top: a copy in the queued item's own language
comes first. A swap with a doubt (:attr:`Stranded.doubts`: another language,
or a match on the name alone) is offered for checking, never pre-ticked.
"""

from __future__ import annotations

from dataclasses import dataclass

from streamselect.core.database import ChannelDB, ProviderDB, WatchQueueDB
from streamselect.core.repositories.channel_live_copy import live_siblings

#: Which unusable sources a scan covers.
SCOPE_EXPIRED = "expired"
SCOPE_ALL = "all"            # expired, switched off, or removed

#: The watch-history columns that move with an item (``ChannelDB``).
HISTORY_FIELDS = ("last_played", "play_count", "watch_progress", "watch_percent",
                  "watch_completed", "last_played_via")
_CLEARED = {"last_played": None, "play_count": 0, "watch_progress": 0, "watch_percent": 0,
            "watch_completed": False, "last_played_via": None}
_QUEUE_FIELDS = ("channel_id", "channel_name", "media_type", "source_id")


@dataclass(frozen=True)
class Copy:
    """One channel, as a row of the window shows it."""

    channel_id: str
    title: str
    language: str        # detected_prefix ("EN"), "" when unknown
    quality: str         # detected_quality, "" when unknown
    year: str
    source: str          # the source's name
    same_language: bool = True


@dataclass(frozen=True)
class Stranded:
    """A queue item on an unusable source, and what it could become."""

    queue_id: int
    old: Copy
    state: str                       # "expired" | "disabled" | "removed"
    candidates: tuple[Copy, ...]     # best first; empty when nothing matches
    reason: str = ""                 # why there is nothing to offer
    by_tmdb: bool = True             # matched on a TMDb id, not on the name alone

    @property
    def best(self) -> Copy | None:
        return self.candidates[0] if self.candidates else None

    @property
    def doubts(self) -> tuple[str, ...]:
        """Why this swap should be looked at before it is made; empty when it is sure.

        Measured on a real queue (2026-11-17): 174 of 176 matches were on a
        TMDb id and two live channels on the name alone, while 70 had a copy
        only in another language — so language is the usual doubt.
        """
        if self.best is None:
            return ()
        out = []
        if not self.best.same_language:
            out.append(f"different language: {self.old.language or 'none'} → "
                       f"{self.best.language or 'none'}")
        if not self.by_tmdb:
            out.append("matched by name only")
        return tuple(out)


def _copy(ch: ChannelDB, sources: dict, same_language: bool = True) -> Copy:
    return Copy(ch.id, ch.detected_title or ch.name or "", ch.detected_prefix or "",
                ch.detected_quality or "", str(ch.detected_year or ""),
                sources.get(ch.provider_id, ch.provider_id), same_language)


def find_stranded(repos, scope: str = SCOPE_ALL, config=None) -> list[Stranded]:
    """Every channel-grain queue item on an unusable source, in queue order.

    Args:
        repos: A ``RepositoryFactory`` on an open session.
        scope: :data:`SCOPE_EXPIRED` for expired sources only, :data:`SCOPE_ALL`
            to add switched-off and removed ones (``get_hidden_provider_ids``).
        config: Ranks copies by the user's version preferences; None skips that.
    """
    providers = repos.providers
    hidden = set(providers.get_hidden_provider_ids())
    expired = set(providers.get_expired_provider_ids())
    inactive = set(providers.get_inactive_provider_ids())
    covered = expired if scope == SCOPE_EXPIRED else hidden
    sources = dict(repos.session.query(ProviderDB.id, ProviderDB.name).all())
    queued = repos.queue.get_queued_ids()
    out = []
    rows = (repos.session.query(WatchQueueDB, ChannelDB)
            .join(ChannelDB, ChannelDB.id == WatchQueueDB.channel_id)
            .filter(WatchQueueDB.episode_id.is_(None))
            .order_by(WatchQueueDB.position).all())
    for row, ch in rows:
        if ch.provider_id not in covered:
            continue
        state = ("expired" if ch.provider_id in expired else
                 "disabled" if ch.provider_id in inactive else "removed")
        old = _copy(ch, sources)
        found = live_siblings(repos, ch, hidden, config)
        lang = ch.detected_prefix or ""
        mine = [c for c in found if (c.detected_prefix or "") == lang]
        other = [c for c in found if (c.detected_prefix or "") != lang]
        candidates = tuple([_copy(c, sources) for c in mine]
                           + [_copy(c, sources, same_language=False) for c in other])
        free = tuple(c for c in candidates if c.channel_id not in queued)
        reason = ("" if free else
                  "Already in your queue from an active source" if candidates else
                  "No copy on your active sources")
        candidates = free
        out.append(Stranded(row.id, old, state, candidates, reason,
                            by_tmdb=(ch.content_key or "").startswith("tmdb:")))
    return out


@dataclass(frozen=True)
class Snapshot:
    """What :func:`replace` changed, for :func:`undo`."""

    queue_rows: tuple[tuple[int, dict], ...]       # (queue_id, its fields before)
    channels: tuple[tuple[str, dict], ...]         # (channel_id, its history before)


def _history(ch: ChannelDB) -> dict:
    return {f: getattr(ch, f) for f in HISTORY_FIELDS}


def _merge_history(old: dict, new: dict) -> dict:
    """The new copy's history once the old copy's moves onto it.

    Plays add up; the more recent copy's resume point, percentage and way of
    playing win; finished stays finished.
    """
    old_last, new_last = old["last_played"], new["last_played"]
    old_newer = old_last is not None and (new_last is None or old_last > new_last)
    recent = old if old_newer else new
    return {
        "last_played": max(d for d in (old_last, new_last) if d) if (old_last or new_last) else None,
        "play_count": (old["play_count"] or 0) + (new["play_count"] or 0),
        "watch_progress": recent["watch_progress"],
        "watch_percent": recent["watch_percent"],
        "watch_completed": bool(old["watch_completed"] or new["watch_completed"]),
        "last_played_via": recent["last_played_via"],
    }


def replace(session, choices: list[tuple[int, str]]) -> tuple[int, int, Snapshot]:
    """Point each chosen queue item at its new copy, moving its watch history.

    Args:
        session: An open, committing session.
        choices: ``(queue_id, new channel_id)`` pairs the user ticked.

    Returns:
        ``(replaced, skipped, snapshot)``: skipped counts items whose new copy
        is already queued (by another item, or earlier in this batch) — they
        are left as they were, never made a duplicate.
    """
    queued = {cid for (cid,) in session.query(WatchQueueDB.channel_id)
              .filter(WatchQueueDB.episode_id.is_(None)).all()}
    rows, channels = [], {}
    replaced = skipped = 0
    for queue_id, new_id in choices:
        row = session.get(WatchQueueDB, queue_id)
        new = session.get(ChannelDB, new_id)
        if row is None or new is None:
            continue
        if new_id in queued:
            skipped += 1
            continue
        old = session.get(ChannelDB, row.channel_id)
        rows.append((queue_id, {f: getattr(row, f) for f in _QUEUE_FIELDS}))
        for ch in (old, new):
            if ch is not None and ch.id not in channels:
                channels[ch.id] = _history(ch)
        if old is not None:
            merged = _merge_history(_history(old), _history(new))
            for f, v in merged.items():
                setattr(new, f, v)
            for f, v in _CLEARED.items():
                setattr(old, f, v)
        queued.discard(row.channel_id)
        queued.add(new_id)
        row.channel_id, row.channel_name = new.id, new.name or ""
        row.media_type, row.source_id = new.media_type or "", new.source_id or ""
        replaced += 1
    return replaced, skipped, Snapshot(tuple(rows), tuple(channels.items()))


def undo(session, snapshot: Snapshot) -> int:
    """Put back every queue item and watch history :func:`replace` changed.

    Returns:
        How many queue items were restored.
    """
    restored = 0
    for queue_id, fields in snapshot.queue_rows:
        row = session.get(WatchQueueDB, queue_id)
        if row is None:
            continue                       # removed from the queue since
        for f, v in fields.items():
            setattr(row, f, v)
        restored += 1
    for channel_id, history in snapshot.channels:
        ch = session.get(ChannelDB, channel_id)
        if ch is not None:
            for f, v in history.items():
                setattr(ch, f, v)
    return restored
