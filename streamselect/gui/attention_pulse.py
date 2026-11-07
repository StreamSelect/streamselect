"""Draw the eye to one control: a soft accent glow that pulses, then goes away.

Used to point at a control the user is being told about elsewhere — the
Exclusions chip after a new source's first scan (user report, R7), and the tour's
stops. A glow (``QGraphicsDropShadowEffect``) rather than a stylesheet change:
it needs no role, leaves the widget's own sheet untouched (so the theme
registry never sees a half-pulsed state), and is removed when it ends.
"""
from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QVariantAnimation
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QWidget

from streamselect.gui import theme as _theme
from streamselect.gui.token_color import to_qcolor

#: One pulse: glow up and back down. Two of them read as "here", not as an alarm.
PULSE_MS = 700
GLOW_RADIUS = 28.0


def pulse(widget: QWidget, times: int = 2) -> QVariantAnimation | None:
    """Pulse an accent glow around *widget* *times* times, then remove it.

    Does nothing when the widget already carries a graphics effect of its own
    (replacing it would destroy it).

    Returns:
        The running animation (kept alive on the widget), or None if skipped.
    """
    if widget.graphicsEffect() is not None:
        return None
    glow = QGraphicsDropShadowEffect(widget)
    glow.setOffset(0, 0)
    glow.setColor(to_qcolor(_theme.COLOR_ACCENT))
    glow.setBlurRadius(0)
    widget.setGraphicsEffect(glow)

    anim = QVariantAnimation(widget)
    anim.setDuration(PULSE_MS)
    anim.setLoopCount(max(1, times))
    anim.setKeyValueAt(0.0, 0.0)
    anim.setKeyValueAt(0.5, GLOW_RADIUS)
    anim.setKeyValueAt(1.0, 0.0)
    anim.setEasingCurve(QEasingCurve.Type.InOutSine)
    anim.valueChanged.connect(lambda v: glow.setBlurRadius(float(v)))

    def _done() -> None:
        if widget.graphicsEffect() is glow:
            widget.setGraphicsEffect(None)
        widget.__dict__.pop("_attention_pulse", None)

    anim.finished.connect(_done)
    widget._attention_pulse = anim      # keep it alive for its run
    anim.start()
    return anim
