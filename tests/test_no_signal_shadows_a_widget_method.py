"""No class declares a signal named like a QWidget method.

A ``hide = pyqtSignal(...)`` on a widget replaced ``QWidget.hide()``: the Sports
view's redraw called ``.hide()`` on a channel list and the app aborted with
"native Qt signal is not callable" (2026-11-12). The census found no other
instance; this keeps it at zero.
"""

from __future__ import annotations

import ast
from pathlib import Path

from PyQt6.QtWidgets import QWidget

ROOT = Path(__file__).resolve().parent.parent / "streamselect"
WIDGET_NAMES = {n for n in dir(QWidget) if not n.startswith("_")}


def _shadowing_signals(source: str) -> list[str]:
    hits = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ClassDef):
            continue
        for st in node.body:
            if (isinstance(st, ast.Assign) and isinstance(st.value, ast.Call)
                    and getattr(st.value.func, "id", "") == "pyqtSignal"):
                hits += [f"{node.name}.{t.id}" for t in st.targets
                         if isinstance(t, ast.Name) and t.id in WIDGET_NAMES]
    return hits


def test_no_signal_is_named_like_a_qwidget_method():
    found = {str(p.relative_to(ROOT)): h for p in ROOT.rglob("*.py")
             if (h := _shadowing_signals(p.read_text(encoding="utf-8")))}
    assert found == {}, f"rename these signals (e.g. hideRequested): {found}"


def test_the_guard_can_fail():
    assert _shadowing_signals("class Row:\n    hide = pyqtSignal(object)\n") == ["Row.hide"]
