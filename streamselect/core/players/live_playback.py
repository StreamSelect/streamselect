"""What a player window is doing right now: its tracks and where it is in its queue.

Read on click for the header's playback menu. Queue names come only from the titles
StreamSelect recorded when it started the queue. mpv's ``playlist`` holds the raw URL, which
can carry a source's credentials, and ``media-title`` falls back to it when no title
was set, so neither is ever read here.
"""
from __future__ import annotations

from dataclasses import dataclass

from streamselect.core.stream_info import language_name

LIVE_PROPS = ["track-list", "playlist-pos", "playlist-count"]
_CHANNEL_NAMES = {1: "mono", 2: "stereo", 6: "5.1", 8: "7.1"}


@dataclass(frozen=True)
class LiveTrack:
    """One audio or subtitle track: mpv's id, a label to show, and whether it is on."""
    track_id: int
    label: str
    selected: bool


@dataclass(frozen=True)
class LivePlayback:
    """One window's tracks and queue. ``readable`` is False when mpv did not answer."""
    key: str | None = None
    readable: bool = False
    audio: tuple[LiveTrack, ...] = ()
    subs: tuple[LiveTrack, ...] = ()
    position: int = 0                       # 1-based place in this window's play queue
    count: int = 0
    current_title: str | None = None
    next_title: str | None = None
    queue_titles: tuple[str | None, ...] = ()   # lines up with the queue, else empty
    content: tuple[str, str] | None = None      # ("episode" | "channel", id) now playing
    watch_queue_place: int | None = None        # 1-based; None = what's playing isn't queued
    watch_queue_total: int | None = None        # None = the Watch Queue section isn't open


def _proper_title(title: object) -> str | None:
    """A title fit to show: never a URL, which is worse than showing no name."""
    text = title.strip() if isinstance(title, str) else ""
    return text if text and "://" not in text else None


def _label(track: dict) -> str:
    """"English · Commentary · AAC · 5.1", or "Track 2" if it names nothing."""
    parts = [language_name(track["lang"])] if track.get("lang") else [f"Track {track.get('id')}"]
    parts.append(track.get("title"))
    if track.get("forced"):
        parts.append("forced")
    if track.get("hearing-impaired"):
        parts.append("CC")
    if track.get("codec"):
        parts.append(str(track["codec"]).upper())
    if track.get("type") == "audio" and track.get("demux-channel-count"):
        channels = track["demux-channel-count"]
        parts.append(_CHANNEL_NAMES.get(channels, f"{channels} channels"))
    return " · ".join(str(p) for p in parts if p)


def _tracks(tracks: list, kind: str) -> tuple[LiveTrack, ...]:
    """The tracks of one kind. ``main-selection`` 1 is mpv's secondary subtitle slot."""
    return tuple(
        LiveTrack(t["id"], _label(t), bool(t.get("selected")) and not t.get("main-selection"))
        for t in tracks
        if isinstance(t, dict) and t.get("type") == kind and t.get("id") is not None)


def live_playback_from_props(key: str | None, props: dict,
                             queue_titles: list | None = None) -> LivePlayback:
    """Turn mpv's answers into what the menu shows.

    Args:
        key: The player instance the properties came from.
        props: ``{name: value}`` for :data:`LIVE_PROPS`; None where mpv did not answer.
        queue_titles: This window's queued titles in order, if StreamSelect started a queue.
            Ignored unless it lines up with mpv's playlist: an item that failed to
            queue would otherwise put the wrong name beside "Next".

    Returns:
        The window's live state.
    """
    tracks = props.get("track-list")
    pos, count = props.get("playlist-pos"), props.get("playlist-count")
    has_pos = isinstance(pos, int) and pos >= 0
    count = count if isinstance(count, int) else 0
    titles: tuple[str | None, ...] = ()
    if queue_titles and has_pos and len(queue_titles) == count and pos < count:
        titles = tuple(_proper_title(title) for title in queue_titles)
    current_title = titles[pos] if titles else None
    next_title = titles[pos + 1] if titles and pos + 1 < count else None
    return LivePlayback(
        key=key,
        readable=isinstance(tracks, list),
        audio=_tracks(tracks or [], "audio"),
        subs=_tracks(tracks or [], "sub"),
        position=pos + 1 if has_pos else 0,
        count=count,
        current_title=current_title,
        next_title=next_title,
        queue_titles=titles,
    )
