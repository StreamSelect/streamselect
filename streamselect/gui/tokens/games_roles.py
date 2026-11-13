"""The Sports view's game cards, live tag, feed rows and guide badge.

Same arrangement as ``tour_roles.py``: a pure function of the tokens, merged
into ``theme`` at import and on every palette switch. Text that already has a
role reuses it (``TEXT_SM_MUTED`` for a card's meta line, ``PANEL_HEADLINE`` /
``PANEL_BODY`` for the empty state); these are only the shapes that had none.
Live is the accent, as the channel list paints a live row's mark, and always
travels with the word LIVE so colour is never the only signal.
"""

from __future__ import annotations

from typing import Mapping


def build(t: Mapping[str, object]) -> dict[str, str]:
    """Compose the game roles from the bound token values."""
    def _(name: str) -> str:
        return str(t[name])

    return {
        # A game. The selected one is outlined in the accent AND drawn heavier.
        "GAME_CARD": (
            f"QFrame#gameCard {{ background: {_('COLOR_BG_CARD')};"
            f" border: 1px solid {_('COLOR_BORDER')}; border-radius: {_('RADIUS_MD')}; }}"
            f"QFrame#gameCard:hover {{ border-color: {_('COLOR_ACCENT')}; }}"
            f"QFrame#gameCard[selected=\"true\"] {{ border: 2px solid {_('COLOR_ACCENT')}; }}"
        ),
        "GAME_TITLE": (
            f"color: {_('COLOR_TEXT_HI')}; font-size: {_('FONT_LG')}; font-weight: 600;"
        ),
        "GAME_LIVE_TAG": (
            f"color: {_('COLOR_ACCENT')}; font-size: {_('FONT_SM')}; font-weight: bold;"
            " letter-spacing: 1px;"
        ),
        # One channel that carries the game: a flat, full-width, left-aligned row.
        "GAME_FEED_ROW": (
            f"QPushButton {{ text-align: left; border: none; background: transparent;"
            f" color: {_('COLOR_TEXT')}; padding: 5px 8px; border-radius: {_('RADIUS_SM')};"
            f" font-size: {_('FONT_MD')}; }}"
            f"QPushButton:hover {{ background: {_('OVERLAY_ACCENT_35')}; color: {_('COLOR_TEXT_HI')}; }}"
        ),
        # "EPG": this listing came from the programme guide, which is less reliable.
        "GAME_GUIDE_CHIP": (
            f"color: {_('COLOR_MUTED_2')}; border: 1px solid {_('COLOR_BORDER')};"
            f" border-radius: {_('RADIUS_SM')}; padding: 0 4px; font-size: {_('FONT_SM')};"
        ),
    }
