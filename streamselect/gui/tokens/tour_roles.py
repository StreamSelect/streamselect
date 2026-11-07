"""The guided tour's callout: the card that explains the highlighted control.

Same arrangement as ``state_roles.py``: a pure function of the tokens, merged
into ``theme`` at import and on every palette switch. The card sits on the
app's own surface ramp (``COLOR_BG_CARD`` / ``COLOR_TEXT_HI``), outlined in the
accent the spotlight ring is drawn in, so the two read as one thing. Its
text uses the shared ``PANEL_HEADLINE``/``PANEL_BODY`` (state_roles.py) and
``TEXT_SM_MUTED`` for the step count — never a twin of an existing role.
"""

from __future__ import annotations

from typing import Mapping


def build(t: Mapping[str, object]) -> dict[str, str]:
    """Compose the tour roles from the bound token values."""
    def _(name: str) -> str:
        return str(t[name])

    return {
        "TOUR_CALLOUT": (
            f"QFrame#tourCallout {{ background: {_('COLOR_BG_CARD')};"
            f" border: 1px solid {_('COLOR_ACCENT')}; border-radius: {_('RADIUS_MD')}; }}"
        ),
        "TOUR_BTN_GHOST": (
            f"QPushButton {{ border: 1px solid {_('COLOR_BORDER')}; background: transparent;"
            f" color: {_('COLOR_TEXT')}; border-radius: {_('RADIUS_SM')}; padding: 5px 12px;"
            f" font-size: {_('FONT_MD')}; }}"
            f"QPushButton:hover {{ color: {_('COLOR_TEXT_HI')}; border-color: {_('COLOR_ACCENT')}; }}"
        ),
    }
