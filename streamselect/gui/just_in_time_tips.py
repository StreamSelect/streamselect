"""Just-in-time tips: explain a control the first time it has something to show.

User report: the tour cannot usefully point at a control that has
nothing in it yet (Explore, on a new install, has no list to open), so such a
control gets a tip at the moment it becomes useful instead — once per profile.
More are planned, one per section view (Discover, EPG, …): each is one entry
in ``TIPS`` and one call to ``show_tip_once`` from wherever its moment is
detected.

A tip is the tour's own overlay with a single card and "Got it"
(``guided_tour.TourOverlay(tip=True)``): the window dims, the real control is
ringed. What has been shown — tips and the tour alike — is ``Config.tips_seen``
(a profile preference, stored in the database).
"""
from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QWidget

from streamselect.gui import deferred_config_save as _cfgsave

#: The key the guided tour records itself under in ``tips_seen``.
TOUR_KEY = "tour"

#: How long a tip waits after its moment, so the layout that triggered it
#: (a list filling in) has settled before the ring is measured.
SETTLE_MS = 600


@dataclass(frozen=True)
class Tip:
    """What a tip says. Where it points is given when it is shown."""

    title: str
    body: str


TIPS: dict[str, Tip] = {
    "explore": Tip(
        "Explore",
        "This number is a button. Click it to open the list in Explore: a "
        "larger view with posters, where you can follow what's similar from "
        "one title to the next. Every list's count does the same.",
    ),
    "playback": Tip(
        "While something plays",
        "This line shows how the stream is doing: how much is buffered, the "
        "download speed and any dropped frames. Click it for the audio track, "
        "subtitles and sound. Normalize volume keeps quiet dialogue and loud "
        "action at a similar level. Downmix audio: choose mono for a single "
        "speaker, stereo for headphones or a pair of speakers.",
    ),
}


def seen(host, key: str) -> bool:
    return key in (getattr(host.config, "tips_seen", None) or [])


def mark_seen(host, key: str) -> None:
    """Record *key* as shown, so it never shows again for this profile."""
    if seen(host, key):
        return
    host.config.tips_seen = [*(host.config.tips_seen or []), key]
    _cfgsave.save_soon(host)


def show_tip_once(host, key: str, target: QWidget) -> bool:
    """Show tip *key* ringing *target*, unless it was shown before.

    Waits ``SETTLE_MS`` and then re-checks everything — the window is up,
    nothing else (the tour, another tip) is on screen, the target is visible —
    because the moment that triggered it is usually mid-layout.

    Returns:
        True when the tip was scheduled.
    """
    if seen(host, key) or key not in TIPS:
        return False
    QTimer.singleShot(SETTLE_MS, lambda: _show_now(host, key, target))
    return True


def _show_now(host, key: str, target: QWidget) -> None:
    from streamselect.gui.guided_tour import TourOverlay, TourStop

    if seen(host, key) or host.__dict__.get("_tour") is not None:
        return
    try:
        ready = host.isVisible() and target.isVisible()
    except RuntimeError:        # the target was deleted while we waited
        return
    if not ready:
        return
    tip = TIPS[key]
    mark_seen(host, key)
    overlay = TourOverlay(host, [TourStop(tip.title, tip.body, lambda _h: target)], tip=True)
    host._tour = overlay
    overlay.finished.connect(lambda: host.__dict__.pop("_tour", None))
    overlay.start()


def offer_explore_tip(host, section) -> None:
    """A sidebar list's count changed: the first time one is above zero, explain it.

    The count IS the way into Explore (the header's arrow is gone), so the tip
    rings that count on the list that just got something in it.
    """
    if seen(host, "explore"):
        return
    count = section.item_count()
    target = section.__dict__.get("_status_label")
    if count and target is not None:
        show_tip_once(host, "explore", target)


def offer_playback_tip(host) -> None:
    """A play has started advancing: the first time, explain the playback line.

    Called on every play's first progress; until the tip has actually been
    shown (the line visible, nothing else on screen) it is not marked seen, so
    a later play tries again.
    """
    target = host.__dict__.get("_playback_health_label")
    if target is not None and not seen(host, "playback"):
        show_tip_once(host, "playback", target)
