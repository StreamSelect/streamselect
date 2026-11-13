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
from typing import Callable

from PyQt6.QtCore import QRect, QTimer
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
    "rating": Tip(
        "Teach it your taste",
        "Like, not interested and dislike. Search for a few things you already "
        "enjoy and like them: Recommended starts finding more like them. Not "
        "interested keeps a title out of your recommendations.",
    ),
    "people": Tip(
        "Cast and crew",
        "Click a name to list everything they're in, across all your sources. "
        "Typing a name in Search finds them too.",
    ),
    "view_epg": Tip(
        "EPG",
        "The TV guide for live channels: what's on now and what's coming up. "
        "Watchlist keeps the shows you follow, On Now shows what's airing, and "
        "Browse lists the schedule.",
    ),
    "view_recommended": Tip(
        "Recommended",
        "Picks based on what you like, watch and favourite. The more you rate, "
        "the better it gets: like or dislike titles from their details.",
    ),
    "view_discover": Tip(
        "Discover",
        "For browsing when you don't have a title in mind: rows of films and "
        "series by genre, decade, actor, collection and more. Click a poster "
        "for its details.",
    ),
    "view_recipe": Tip(
        "Recipe",
        "Narrow everything down by what you pick. Click tags, such as a genre, "
        "a language and a decade, and the matching titles appear below. Save "
        "a recipe to come back to it.",
    ),
}

#: Which tip each content view gets the first time it opens, and the nav
#: chip it rings (the chip the user just clicked).
VIEW_TIPS: dict[str, tuple[str, str]] = {
    "epg": ("view_epg", "epg_chip"),
    "preferences": ("view_recommended", "prefs_chip"),
    "discover": ("view_discover", "discover_chip"),
    "recipe": ("view_recipe", "recipe_chip"),
}


def seen(host, key: str) -> bool:
    return key in (getattr(host.config, "tips_seen", None) or [])


def mark_seen(host, key: str) -> None:
    """Record *key* as shown, so it never shows again for this profile."""
    if seen(host, key):
        return
    host.config.tips_seen = [*(host.config.tips_seen or []), key]
    _cfgsave.save_soon(host)


def reset_tips(host) -> int:
    """Forget which tips were shown, so each shows again at its moment.

    Tools ▸ Show tips again. The tour's own key is kept: the tour is offered
    from its menu entry, not by a moment.

    Returns:
        How many tips were reset.
    """
    kept = [k for k in (host.config.tips_seen or []) if k == TOUR_KEY]
    count = len(host.config.tips_seen or []) - len(kept)
    host.config.tips_seen = kept
    _cfgsave.save_soon(host)
    return count


def show_tip_once(host, key: str, target: QWidget,
                  area: Callable[[QWidget], QRect] | None = None) -> bool:
    """Show tip *key* ringing *target*, unless it was shown before.

    Waits ``SETTLE_MS`` and then re-checks everything — the window is up,
    nothing else (the tour, another tip) is on screen, the target is visible —
    because the moment that triggered it is usually mid-layout.

    Returns:
        True when the tip was scheduled.
    """
    if seen(host, key) or key not in TIPS:
        return False
    QTimer.singleShot(SETTLE_MS, lambda: _show_now(host, key, target, area))
    return True


def _show_now(host, key: str, target: QWidget, area=None) -> None:
    from streamselect.gui.guided_tour import TourOverlay, TourStop

    if seen(host, key) or host.__dict__.get("_tour") is not None:
        return
    try:
        # On screen, not merely shown: a cast name scrolled below the details
        # pane's viewport waits for a later title (an unshown tip is not "seen").
        ready = host.isVisible() and target.isVisible() and not target.visibleRegion().isEmpty()
    except RuntimeError:        # the target was deleted while we waited
        return
    if not ready:
        return
    tip = TIPS[key]
    mark_seen(host, key)
    overlay = TourOverlay(host, [TourStop(tip.title, tip.body, lambda _h: target, area=area)],
                          tip=True)
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


def offer_view_tip(host, view: str) -> None:
    """A content view was switched to: the first time, explain it, ringing its chip."""
    key, chip = VIEW_TIPS.get(view, (None, None))
    target = host.__dict__.get(chip) if chip else None
    if target is not None and not seen(host, key):
        show_tip_once(host, key, target)


def _span(buttons: list[QWidget]) -> Callable[[QWidget], QRect]:
    """The rect covering *buttons*, in their shared parent's coordinates."""
    def area(_parent: QWidget) -> QRect:
        rect = QRect()
        for b in buttons:
            rect = rect.united(b.geometry())
        return rect
    return area


def offer_details_tips(host) -> None:
    """The details pane has filled with a title: explain rating, then cast.

    One tip at a time — ``_show_now`` skips while another is on screen, and
    an unshown tip is not marked seen — so the cast tip waits for a later
    title once the rating tip has shown.
    """
    pane = host.__dict__.get("details_pane")
    if pane is None:
        return
    bar = pane.__dict__.get("_action_bar")
    if bar is not None and not seen(host, "rating"):
        buttons = [bar.like_button, bar.not_interested_button, bar.dislike_button]
        parent = bar.like_button.parentWidget()
        if all(b.isVisibleTo(host) and b.parentWidget() is parent for b in buttons):
            show_tip_once(host, "rating", parent, area=_span(buttons))
            return
    cast = pane.__dict__.get("_cast")
    if cast is not None and not seen(host, "people"):
        chips = cast.person_chips("director") + cast.person_chips("cast")
        if chips and chips[0].isVisibleTo(host):
            show_tip_once(host, "people", chips[0])
