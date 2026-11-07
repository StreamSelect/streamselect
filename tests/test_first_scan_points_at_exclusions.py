"""After a new source's first scan, point at the Exclusions chip (user report, R7).

A notification names what the source brought in and where to hide it
everywhere, with an Open Exclusions button, and the chip itself pulses twice.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QPushButton


@pytest.mark.parametrize(("first", "ok", "announced"), [
    (True, True, True), (True, False, False), (False, True, False)])
def test_only_a_new_sources_successful_first_load_announces(first, ok, announced):
    from streamselect.gui.main_window import MainWindow

    host = MagicMock()
    host.active_threads = []
    host.refreshing_providers = set()
    if first:
        host.__dict__["_first_loading"] = {"p1": "Example"}
    MainWindow._on_queue_refresh_finished(host, "p1", ok, "done", None)
    assert host._announce_first_scan.called is announced
    assert "p1" not in (host.__dict__.get("_first_loading") or {}), "the first load is over"


def test_the_notice_names_the_counts_and_opens_exclusions(qapp, owned_widgets):
    from streamselect.core.notifications import NotificationManager
    from streamselect.gui.main_window_source_add import _SourceAddMixin

    host = MagicMock()
    host.config.tips_seen = []
    host.notification_manager = NotificationManager()
    chip = owned_widgets.own(QPushButton("Exclusions"))
    host.__dict__["_filter_chip"] = chip
    _SourceAddMixin._show_first_scan_notice(host, 12, 1)

    (note,) = host.notification_manager.get_visible_notifications()
    assert note.message.startswith("Found 12 regions and 1 language.")
    assert "Exclusions in the top bar" in note.message
    label, callback = note.actions[0][:2]
    assert label == "Open Exclusions"
    callback()
    host._open_global_filter_dialog.assert_called_once()
    assert chip.graphicsEffect() is not None, "the chip pulses"


def test_the_pulse_glows_then_leaves_nothing_behind(qapp, owned_widgets):
    from streamselect.gui.attention_pulse import pulse

    widget = owned_widgets.own(QPushButton("Exclusions"))
    widget.show()
    assert pulse(widget) is not None
    peak = 0.0
    end = time.time() + 0.8
    while time.time() < end:
        qapp.processEvents()
        effect = widget.graphicsEffect()
        peak = max(peak, effect.blurRadius() if effect else 0.0)
        time.sleep(0.02)
    assert peak > 10, "no visible glow"
    end = time.time() + 2
    while widget.graphicsEffect() is not None and time.time() < end:
        qapp.processEvents()
        time.sleep(0.02)
    assert widget.graphicsEffect() is None, "the glow outlived the pulse"
