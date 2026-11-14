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
            # Only one collection lists it (Level 2): dashed, the app's "guessed" mark.
            f"QFrame#gameCard[certain=\"false\"] {{ border-style: dashed; }}"
        ),
        # The card's "▶ [US] STATION" line: one click plays, so it lights on hover.
        "GAME_PLAY_LINE": (
            f"QFrame#gamePlayLine {{ border-radius: {_('RADIUS_SM')}; }}"
            f"QFrame#gamePlayLine:hover {{ background: {_('OVERLAY_ACCENT_35')}; }}"
        ),
        # One channel in an open card: clicking its name plays it.
        "GAME_CHANNEL_ROW": (
            f"QWidget#gameChannelRow {{ border-radius: {_('RADIUS_SM')}; }}"
            f"QWidget#gameChannelRow:hover {{ background: {_('OVERLAY_10')}; }}"
        ),
        # PLAYING, in the details pane's playing colour (DETAIL_PLAY_BTN_PLAYING).
        "GAME_PLAYING": (
            f"color: {_('COLOR_OK')}; font-size: {_('FONT_SM')}; font-weight: bold; letter-spacing: 1px;"
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
            # A game you have an alert on: the guide's watch-list look
            # (epg_widgets.apply_watchlist_highlight), on rows and cards (SV-Q51).
            f"QPushButton[alerted=\"true\"] {{ color: {_('COLOR_ACCENT_HOVER')}; font-weight: bold; }}"
            f"QPushButton[alerted=\"true\"]:hover {{ color: {_('COLOR_TEXT_HI')}; }}"
        ),
        # A card's title: PANEL_HEADLINE's look, and the watch-list colour, bold,
        # when you have an alert on the game (SV-Q51) — the same alerted state as
        # GAME_FEED_ROW's, so a row and a card say it alike.
        "GAME_CARD_TITLE": (
            f"QLabel {{ color: {_('COLOR_TEXT_HI')}; font-size: {_('FONT_LG')}; font-weight: 600; }}"
            f"QLabel[alerted=\"true\"] {{ color: {_('COLOR_ACCENT_HOVER')}; font-weight: bold; }}"
        ),
        # The games list's time column (SV-Q45/46): the group's time, and the muted
        # echo a hovered row shows of its own time in its otherwise empty cell.
        "GAME_TIME": f"color: {_('COLOR_TEXT')}; font-size: {_('FONT_MD')}; padding: 5px 0;",
        "GAME_TIME_ECHO": f"color: {_('COLOR_MUTED_2')}; font-size: {_('FONT_MD')}; padding: 5px 0;",
        # Every other start-time group: a very faint tint, below the header band's
        # OVERLAY_10 and well apart from a hovered row's accent (SV-Q47).
        "GAME_TIME_GROUP": (
            f"QWidget#gameTimeGroup {{ background: {_('OVERLAY_04')}; border-radius: {_('RADIUS_SM')}; }}"
        ),
        # A finished game from an earlier day: the same line as GAME_FEED_ROW, but plain
        # text — its channels have moved on, so nothing to open (owner, 2026-11-13).
        "GAME_ROW_PAST": (
            f"color: {_('COLOR_TEXT')}; padding: 5px 8px; font-size: {_('FONT_MD')};"
            f" background: transparent;"
        ),
        # "EPG": this listing came from the programme guide, which is less reliable.
        "GAME_GUIDE_CHIP": (
            f"color: {_('COLOR_MUTED_2')}; border: 1px solid {_('COLOR_BORDER')};"
            f" border-radius: {_('RADIUS_SM')}; padding: 0 4px; font-size: {_('FONT_SM')};"
        ),
    }
