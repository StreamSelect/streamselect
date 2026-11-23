"""The "Still watching?" question is never clipped (owner, 2026-11-23).

The dialog had no width, so Qt guessed its wrapped label's height and cut off the
first line of the question ("The queue auto-advanced through 7 more episodes.").
"""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel

from streamselect.gui.queue_end_prompt import PROMPT_MIN_WIDTH, build_queue_end_dialog


def _question(dlg) -> QLabel:
    return next(w for w in dlg.findChildren(QLabel) if w.text().startswith("The queue auto-advanced"))


def test_the_whole_question_is_shown(qapp, owned_widgets):
    for count, first in ((7, True), (1, False), (24, True)):
        dlg, _tick = build_queue_end_dialog(None, count, first, lambda _l: None)
        owned_widgets.own(dlg)
        dlg.show()
        qapp.processEvents()
        msg = _question(dlg)
        assert dlg.width() >= PROMPT_MIN_WIDTH
        assert msg.height() >= msg.heightForWidth(msg.width()), "every wrapped line has room"
        assert msg.geometry().top() >= dlg.layout().contentsMargins().top(), "nothing cut off at the top"
        assert dlg.height() >= dlg.sizeHint().height()
        dlg.close()


def test_the_tick_is_offered_only_when_the_run_had_a_first_episode(qapp, owned_widgets):
    dlg, tick = build_queue_end_dialog(None, 3, True, lambda _l: None)
    owned_widgets.own(dlg)
    assert tick is not None and tick.isChecked()
    dlg2, tick2 = build_queue_end_dialog(None, 3, False, lambda _l: None)
    owned_widgets.own(dlg2)
    assert tick2 is None
