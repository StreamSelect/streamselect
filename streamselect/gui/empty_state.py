"""Why a view is empty — one wording table and one panel, for every view.

A user (Q2/Q11/R6 and): with zero sources every view
shows a proper empty state and hides nothing, and "no content at all" is not
"no results". Five states, worded the same wherever they appear:

==================  ==========================================  =============
State               Says                                        Action
==================  ==========================================  =============
NO_SOURCE           there's no source to read from (and why)    Add / Open Sources
FIRST_LOAD          Loading <source>… channels appear …         —
NOTHING_HERE        This source has no channels                 Open Sources
NO_RESULTS          No results for "<query>"                    Clear search
FILTERED            N titles are hidden by your filters         (the per-filter
                                                                buttons above)
==================  ==========================================  =============

The first two are about the SOURCES, so they show in every content view (the
host decides them once, ``main_window_empty_state``); the last three are about
one view's own result. The no-source notice in the corner words its cause with
``no_source_notice_text`` below, so the notice and the panel cannot disagree.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from enum import Enum

from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from streamselect.core.repositories.dtos import SourceAvailability
from streamselect.core.time_display import date_text
from streamselect.gui import theme as _theme
from streamselect.gui.flow_layout import FlowLayout


class EmptyState(Enum):
    """The five reasons a view can be empty."""

    NO_SOURCE = "no_source"
    FIRST_LOAD = "first_load"
    NOTHING_HERE = "nothing_here"
    NO_RESULTS = "no_results"
    FILTERED = "filtered"


def no_source_notice_text(avail: SourceAvailability) -> tuple[str, str, str] | None:
    """Why no source is usable, by cause — or None when one is.

    A user (Q3/R5): worded by cause, including every source turned off by the
    user (the result is the same — nothing to show — and the notice names why).

    Returns:
        ``(title, message, action)``; *action* is ``"add"`` (Add Source) when
        there is no source at all, else ``"open"`` (Open Sources), where the
        fix for an expired or switched-off source is.
    """
    if avail.usable:
        return None
    if not avail.total:
        return ("No sources available", "Add a source to load channels.", "add")
    if avail.expired and avail.expired == avail.total:
        if avail.total == 1 and avail.last_expired_at:
            title = f"Your source expired on {date_text(avail.last_expired_at)}"
        else:
            title = f"All {avail.total} sources have expired"
        return (title, "Renew with your provider, or add another source.", "open")
    if avail.turned_off == avail.total and not avail.expired:
        title = ("Your source is turned off" if avail.total == 1
                 else f"All {avail.total} sources are turned off")
        return (title, "Turn one on in Sources to see its channels.", "open")
    return ("No source is usable",
            f"{avail.total - avail.expired} turned off, {avail.expired} expired. "
            "Open Sources to turn one on or add another.", "open")


def empty_state_text(state: EmptyState, *, avail: SourceAvailability | None = None,
                     names: Sequence[str] = (), sources: int = 1, query: str = "",
                     hidden: int = 0) -> tuple[str, str, str | None]:
    """The headline, hint and action key for one empty state.

    Args:
        state: Which of the five.
        avail: NO_SOURCE only — the counts the cause is worded from.
        names: FIRST_LOAD only — the sources loading for the first time.
        sources: NOTHING_HERE only — how many usable sources there are.
        query: NO_RESULTS only — what was searched.
        hidden: FILTERED only — how many results the filters hide.

    Returns:
        ``(headline, hint, action)``; *action* is ``"add"``, ``"open"``,
        ``"clear_search"`` or ``None``.
    """
    if state is EmptyState.NO_SOURCE:
        cause = no_source_notice_text(avail) if avail else None
        title, message, action = cause or ("No sources available", "", "add")
        return ("Nothing to show yet: there's no source to read from.",
                f"{title}. {message}".strip(), action)
    if state is EmptyState.FIRST_LOAD:
        who = " and ".join(names) or "your source"
        return (f"Loading {who}…", "Channels appear here as they arrive.", None)
    if state is EmptyState.NOTHING_HERE:
        headline = ("This source has no channels." if sources == 1
                    else "Your sources have no channels.")
        return (headline, "Check with your provider, or refresh the source in Sources.", "open")
    if state is EmptyState.NO_RESULTS:
        return (f"No results for “{query}”.",
                "Check the spelling, or clear the search.", "clear_search")
    return (f"{hidden:,} {'title is' if hidden == 1 else 'titles are'} hidden by your filters.",
            "Show them with the buttons above, one kind at a time.", None)


class EmptyStatePanel(QFrame):
    """The one panel a view uses to say why it is empty, with its action."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("emptyStatePanel")
        _theme.style(self, "EMPTY_STATE_PANEL")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        self.headline = QLabel()
        self.headline.setWordWrap(True)
        _theme.style(self.headline, "PANEL_HEADLINE")
        layout.addWidget(self.headline)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        _theme.style(self.hint, "PANEL_BODY")
        layout.addWidget(self.hint)
        self._actions = QWidget()
        self._actions_layout = FlowLayout(self._actions, spacing=6)
        self._actions_layout.setContentsMargins(0, 4, 0, 0)
        self._buttons: list[QPushButton] = []
        layout.addWidget(self._actions)
        self.hide()

    def show_state(self, headline: str, hint: str,
                   actions: Sequence[tuple[str, Callable[[], object], str]] = ()) -> None:
        """Say why the view is empty and offer what fixes it.

        Each action is ``(label, callback, tooltip)``.
        """
        self.headline.setText(headline)
        self.hint.setText(hint)
        self.hint.setVisible(bool(hint))
        while self._actions_layout.takeAt(0) is not None:
            pass
        for old in self._buttons:
            old.hide()
            old.deleteLater()
        self._buttons = []
        for label, callback, tip in actions:
            btn = QPushButton(label)
            btn.setToolTip(tip)
            _theme.style(btn, "EMPTY_STATE_BTN")
            btn.clicked.connect(lambda _=False, cb=callback: cb())
            self._actions_layout.addWidget(btn)
            self._buttons.append(btn)
        self._actions.setVisible(bool(actions))
        self.show()

    def buttons(self) -> list[QPushButton]:
        """The action buttons on show now."""
        return list(self._buttons)
