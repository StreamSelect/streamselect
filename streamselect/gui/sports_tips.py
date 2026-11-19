"""The Sports view's first-time help: a short tour, then one-off tips at their moments.

Owner, 2026-11-18 (TQ1-TQ4): the tour starts on its own the first time Sports
shows games — the sport header, the league chips, a league's banner, a game, its
bell, and the toolbar (Less certain explained). Settings is not in it: the app
should be tuned so most people never need Settings. Then each one-off tip shows
the first time its moment comes: a game's channel list opens, a finished game's
bell is on screen, a finished game can still be put back ("still on"), a league
is hidden, and in Settings ▸ Sports a game's length is changed.

The tips are ``just_in_time_tips.TIPS`` entries (``sports_*``) (once per profile, ``Config.tips_seen``;
Tools ▸ Show tips again resets them, the Sports tour included). The tour is the
guided tour's own overlay with these stops. A stop whose control is not on screen
(no game on now) is left out; a tip whose control is not on screen waits for a
later moment, unseen.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QRect, QTimer
from PyQt6.QtWidgets import QWidget

from streamselect.gui.just_in_time_tips import SETTLE_MS, mark_seen, seen, show_tip_once

#: ``tips_seen`` key of the Sports tour.
SPORTS_TOUR_KEY = "sports_tour"



def _stops(view) -> list:
    """The tour's stops for what *view* shows now; a stop with nothing to ring is left out."""
    from streamselect.gui.guided_tour import TourStop

    def area_of(widgets: list[QWidget]):
        def area(_parent: QWidget) -> QRect:
            rect = QRect()
            for w in widgets:
                rect = rect.united(w.geometry())
            return rect
        return area

    out = []
    header = next((w for k, w in view.headers.items() if k.startswith("sport:")), None)
    if header is not None:
        out.append(TourStop(
            "Sports", "Each sport has its own section with every game on now and still to come. "
            "Click its header to collapse it. The sports and leagues you watch most come "
            "first.", lambda _h, w=header: w))
    toggles = [c.parentWidget() for c in view.league_chips.values()]
    toggles = [t for t in toggles if header is not None and t.parentWidget() is header]
    if toggles:
        out.append(TourStop(
            "Leagues", "Click a league to hide it from this list, and click it again to bring "
            "it back. A dot and a number mean games are on now.",
            lambda _h, w=header: w, area=area_of(toggles)))
    banner = next((w for k, w in view.headers.items()
                   if ":league:" in k and not k.endswith(":panel")), None)
    if banner is not None:
        out.append(TourStop(
            "A league", "Each league lists its games on now, the days to come and Finished. "
            "Click its name to collapse it. The chip says how many games are on now, or "
            "when the next one starts.", lambda _h, w=banner: w))
    card = view.cards[0] if view.cards else None
    if card is not None:
        out.append(TourStop(
            "A game on now", "Click a game to list every channel showing it; double-click to "
            "play the best one. The bar shows how far into the game it is, and turns "
            "yellow when the game is likely ending.", lambda _h, w=card: w))
    bell = card.bell if card is not None else next(
        (r.bell for r in view.rows if not getattr(r, "finished", False)), None)
    if bell is not None:
        out.append(TourStop(
            "Alerts", "Click the bell to be told when this game starts. Right-click it for "
            "every game of either team, or whenever these two meet.", lambda _h, w=bell: w))
    if view.toolbar is not None:
        out.append(TourStop(
            "How games are listed", "By sport groups games by sport and league; By time "
            "lists every sport together in start order. Most watched or A–Z orders the "
            "sports and leagues. Less certain games adds games only one source lists: "
            "they may be at a different time, or not happen at all, so they have a "
            "dashed outline.", lambda _h, w=view.toolbar: w))
    return out


def offer_sports_tour(host, view) -> bool:
    """The first time Sports shows games, start its tour. Returns True when scheduled."""
    if seen(host, SPORTS_TOUR_KEY) or not (view.cards or view.rows):
        return False
    QTimer.singleShot(SETTLE_MS, lambda: _start_tour(host, view))
    return True


def _start_tour(host, view) -> None:
    from streamselect.gui.guided_tour import TourOverlay

    if seen(host, SPORTS_TOUR_KEY) or host.__dict__.get("_tour") is not None:
        return
    try:
        if not (host.isVisible() and view.isVisible()):
            return
    except RuntimeError:           # the view went while we waited
        return
    stops = _stops(view)
    if not stops:
        return
    mark_seen(host, SPORTS_TOUR_KEY)
    overlay = TourOverlay(host, stops)
    overlay._end_btn.setToolTip("Stop here. Tools ▸ Show tips again shows it again.")
    host._tour = overlay
    overlay.finished.connect(lambda: host.__dict__.pop("_tour", None))
    overlay.start()


def _first(rows: list, pred) -> Optional[QWidget]:
    return next((r for r in rows if pred(r)), None)


def on_rendered(host, view) -> None:
    """The Sports list was rebuilt: the tour first, then whichever tip's moment is here."""
    if offer_sports_tour(host, view):
        return
    if not seen(host, SPORTS_TOUR_KEY):
        return                    # the tour comes first; tips wait until it has shown
    if view.open_list is not None and not seen(host, "sports_channels"):
        show_tip_once(host, "sports_channels", view.open_list)
        return
    finished = _first(view.rows, lambda r: getattr(r, "finished", False))
    if finished is not None and not seen(host, "sports_finished_bell"):
        show_tip_once(host, "sports_finished_bell", finished.bell)
        return
    still_on = _first(view.rows, lambda r: getattr(r, "still_on", False))
    if still_on is not None and not seen(host, "sports_still_on"):
        show_tip_once(host, "sports_still_on", still_on.parentWidget())


def on_league_hidden(host, view, sport: str, league: str) -> None:
    chip = view.league_chips.get((sport, league))
    if chip is not None:
        show_tip_once(host, "sports_league_hidden", chip.parentWidget())
