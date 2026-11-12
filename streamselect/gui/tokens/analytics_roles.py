"""The Sources editor's Analytics tab: its stat blocks and its one-line verdicts.

Same arrangement as ``state_roles.py``: a pure function of the tokens, merged
into ``theme`` at import and on every palette switch. A stat block is a figure
over its caption (``META_HINT``); the figure is a step below the headline
tiles' ``STAT_FIGURE`` so a card's numbers do not compete with the tiles.
"""

from __future__ import annotations

from typing import Mapping


def build(t: Mapping[str, object]) -> dict[str, str]:
    """Compose the analytics roles from the bound token values."""
    def _(name: str) -> str:
        return str(t[name])

    return {
        "STAT_FIGURE_MD": (
            f"color: {_('COLOR_TEXT_HI')}; font-size: {_('FONT_XL')}; font-weight: 700;"
        ),
        # A sentence that says what the numbers mean, set off by an accent edge
        # on the card's own tint (a translucent tint, so the surface ramp's text).
        "ANALYTICS_VERDICT": (
            f"QLabel {{ color: {_('COLOR_TEXT_HI')}; font-size: {_('FONT_MD')};"
            f" background: {_('OVERLAY_05')}; border-left: 3px solid {_('COLOR_ACCENT')};"
            f" border-radius: {_('RADIUS_SM')}; padding: 7px 10px; }}"
        ),
    }
