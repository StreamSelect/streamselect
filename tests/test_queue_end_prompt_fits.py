"""The "Still watching?" prompt: three answers, the whole question, and when it asks.

Owner, 2026-11-23: the question was clipped (the dialog had no width); "I watched
the first episode, too" was "dumb language" — it should be three buttons, None ·
First only · All, under "How many did you watch?"; and it should be asked only for a
run started in hours you might fall asleep (default 9 PM to 5 AM), not every time.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QCheckBox, QLabel, QPushButton

from streamselect.gui.queue_end_prompt import (
    ALL, FIRST_ONLY, NONE, PROMPT_MIN_WIDTH, asks_now, build_queue_end_dialog,
)


def _dialog(owned_widgets, count=7):
    dlg = build_queue_end_dialog(None, count, lambda _l: None)
    owned_widgets.own(dlg)
    dlg.show()
    return dlg


def _buttons(dlg) -> list[QPushButton]:
    """The answer buttons, left to right as drawn."""
    btns = [b for b in dlg.findChildren(QPushButton) if b.text() in ("None", "First only", "All")]
    return sorted(btns, key=lambda b: b.mapTo(dlg, QPoint(0, 0)).x())


def test_three_answers_in_order_with_all_on_enter(qapp, owned_widgets):
    dlg = _dialog(owned_widgets)
    qapp.processEvents()
    btns = _buttons(dlg)
    assert [b.text() for b in btns] == ["None", "First only", "All"]
    assert btns[2].isDefault(), "Enter keeps the run, as Yes did"
    assert not dlg.findChildren(QCheckBox), "no tick box any more"
    question = next(w for w in dlg.findChildren(QLabel) if "How many did you watch?" in w.text())
    assert "7 more episodes after the one you started" in question.text()


@pytest.mark.parametrize("label, choice", [("None", NONE), ("First only", FIRST_ONLY), ("All", ALL)])
def test_each_button_records_its_answer_and_closes(qapp, owned_widgets, label, choice):
    dlg = _dialog(owned_widgets)
    next(b for b in _buttons(dlg) if b.text() == label).click()
    assert dlg.choice == choice and not dlg.isVisible()


def test_closing_it_answers_nothing(qapp, owned_widgets):
    dlg = _dialog(owned_widgets)
    dlg.reject()
    assert dlg.choice is None


def test_the_whole_question_is_shown(qapp, owned_widgets):
    for count in (1, 7, 24):
        dlg = _dialog(owned_widgets, count)
        qapp.processEvents()
        msg = next(w for w in dlg.findChildren(QLabel) if "How many" in w.text())
        assert dlg.width() >= PROMPT_MIN_WIDTH
        assert msg.height() >= msg.heightForWidth(msg.width()), "every wrapped line has room"
        dlg.close()


def _cfg(**kw):
    base = {"prompt_after_autoplay": True, "autoplay_prompt_night_only": True,
            "autoplay_prompt_hours": "21:00-05:00"}
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.mark.parametrize("hh, mm, asked", [
    (21, 0, True), (23, 30, True), (2, 15, True), (4, 59, True),   # the night, across midnight
    (5, 0, False), (14, 0, False), (20, 59, False),                 # the day
])
def test_by_default_it_asks_only_for_a_run_started_at_night(hh, mm, asked):
    assert asks_now(_cfg(), datetime(2026, 11, 23, hh, mm)) is asked


def test_a_window_inside_one_day_works_too():
    cfg = _cfg(autoplay_prompt_hours="13:00-17:00")
    assert asks_now(cfg, datetime(2026, 11, 23, 14, 0))
    assert not asks_now(cfg, datetime(2026, 11, 23, 18, 0))


def test_any_time_when_night_only_is_off_and_never_when_asking_is_off():
    assert asks_now(_cfg(autoplay_prompt_night_only=False), datetime(2026, 11, 23, 14, 0))
    assert not asks_now(_cfg(prompt_after_autoplay=False), datetime(2026, 11, 23, 23, 0))


def test_a_garbled_setting_asks_rather_than_silently_never_asking():
    assert asks_now(_cfg(autoplay_prompt_hours="late"), datetime(2026, 11, 23, 14, 0))


def test_the_setting_is_on_the_sidebar_page_beside_history_and_saves(qtbot, monkeypatch):
    from PyQt6.QtCore import QTime

    from streamselect.core.config import Config
    from streamselect.gui.settings_dialog import SettingsDialog

    monkeypatch.setattr(Config, "save", lambda *a, **k: None)
    cfg = Config()
    assert (cfg.autoplay_prompt_night_only, cfg.autoplay_prompt_hours) == (True, "21:00-05:00")
    dlg = SettingsDialog(cfg)
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.select_setting("Sidebar", "Ask how many episodes")
    qtbot.waitUntil(lambda: dlg._autoplay_until_time.isVisible())
    assert dlg._autoplay_when_combo.currentText() == "only between"
    assert dlg._autoplay_from_time.time() == QTime(21, 0) and dlg._autoplay_until_time.time() == QTime(5, 0)
    dlg._autoplay_from_time.setTime(QTime(22, 30))
    dlg._prompt_after_autoplay_check.setChecked(False)
    assert not dlg._autoplay_from_time.isEnabled(), "no hours to set when it never asks"
    dlg._prompt_after_autoplay_check.setChecked(True)
    dlg._save_values()
    assert cfg.autoplay_prompt_hours == "22:30-05:00" and cfg.prompt_after_autoplay is True
