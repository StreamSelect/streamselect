"""The empty-state panel's roles: one look for "why is there nothing here".

Every content view says why it is empty in the same panel
(``streamselect.gui.empty_state``), so its sheet is one role family rather than a
look per view. Same arrangement as ``chip_roles.py`` and ``detail_roles.py``:
a pure function of the tokens, merged into ``theme`` at import and on every
palette switch.

The look is the zero-sources banner's, which these replace: a blue tint
of the app surface, the text on the surface's own ramp (a translucent tint is
not a solid fill, so ``on_fill`` does not apply), and an outlined accent button.
"""

from __future__ import annotations

from typing import Mapping


def build(t: Mapping[str, object]) -> dict[str, str]:
    """Compose the empty-state roles from the bound token values."""
    def _(name: str) -> str:
        return str(t[name])

    return {
        # The panel. Selected by object name so the tint does not cascade into
        # every child label's background.
        "EMPTY_STATE_PANEL": (
            f"QFrame#emptyStatePanel {{ background: {_('OVERLAY_BLUE_10')};"
            f" border-radius: {_('RADIUS_MD')}; }}"
        ),
        # Headline and body text of a panel or card that explains something —
        # this one, and the tour's callout (tour_roles.py) — one pair, not a
        # twin per surface (test_theme_role_duplication).
        "PANEL_HEADLINE": (
            f"color: {_('COLOR_TEXT_HI')}; font-size: {_('FONT_LG')}; font-weight: 600;"
        ),
        "PANEL_BODY": f"color: {_('COLOR_TEXT')}; font-size: {_('FONT_MD')};",
        "EMPTY_STATE_BTN": (
            f"QPushButton {{ border: 1px solid {_('COLOR_ACCENT_BLUE')};"
            f" border-radius: {_('RADIUS_SM')}; padding: 4px 12px;"
            f" font-size: {_('FONT_MD')}; font-weight: 600;"
            f" background: {_('OVERLAY_BLUE_20')}; color: {_('COLOR_ACCENT_BLUE')}; }}"
            f"QPushButton:hover {{ background: {_('OVERLAY_BLUE_40')};"
            f" color: {_('COLOR_TEXT_HI')}; }}"
        ),
    }
