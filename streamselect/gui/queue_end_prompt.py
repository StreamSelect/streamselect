"""The "Still watching?" end-of-queue confirmation (extracted from ``_StreamingMixin``).

When a queued auto-advance run ends, the off-thread checkpoint tick emits
``_queue_end_detected`` with the ids of every episode the playlist advanced
PAST — those were already written 100%-complete by ``_bg_finalise_episode``
while the queue was still running.  This mixin owns the main-thread prompt that
asks how many the user actually watched — None · First only · All — and the
answers' write paths. It is asked only when ``asks_now`` says so (by default for a
run that reaches 21:00-05:00, Settings ▸ Sidebar ▸ History).

Every answer writes, and every one refreshes
--------------------------------------------
"None" and "First only" **must undo the auto-mark** — "No" once
used to only downgrade ``last_played_via`` to ``'queue'`` (a greyer glyph) and
leave the episodes flagged watched, which is the opposite of the answer given.
Every write here ends by emitting ``_episode_watch_state_changed`` so the open
series tree re-reads those rows: the auto-mark writes happen off-thread while
the tree is already on screen, and a tree that never hears about them shows a
watch state that is simply out of date (an earlier change — the user then acts on the stale
view, unmarking the episodes it *did* show and leaving the ones it did not, so
the season ends up with an unwatched hole in the middle of a watched run).
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from loguru import logger
from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout

from streamselect.core.repositories import RepositoryFactory
from streamselect.gui.dialog_chrome import action_button, dialog_buttons

#: Where the prompt's link opens Settings: the row that says when it is asked.
PROMPT_SETTING_LINK = "settings:Sidebar/Ask how many episodes"
#: The prompt's width: room for its question on a line or two. Without one the
#: dialog took its wrapped label's guessed height and clipped the question's first
#: line (owner, 2026-11-23).
PROMPT_MIN_WIDTH = 380
#: The three answers (owner, 2026-11-23: three buttons, not a question and a tick).
#: Closing the dialog answers nothing: the run stays as the queue marked it.
NONE, FIRST_ONLY, ALL = "none", "first", "all"


def _hhmm(text: str) -> time:
    hours, minutes = text.strip().split(":")
    return time(int(hours), int(minutes))


def asks_now(config, started: datetime, ended: datetime | None = None) -> bool:
    """Whether a run from ``started`` to ``ended`` gets the question: asking is on,
    and either it asks at any hour or some part of the run fell inside the hours set
    (which may wrap past midnight, as the default 21:00-05:00 does). A garbled
    setting asks.

    Any part, not the start: a run started at 7:14 PM that the queue carried on to
    11 PM is the one you fell asleep in, and asking only by its start never asked
    (owner, 2026-11-25)."""
    if not config.prompt_after_autoplay:
        return False
    if not config.autoplay_prompt_night_only:
        return True
    try:
        start, end = (_hhmm(t) for t in config.autoplay_prompt_hours.split("-"))
    except (ValueError, AttributeError):
        return True
    ended = max(ended or started, started)

    t = started.time()
    if (start <= t or t < end) if start > end else (start <= t < end):
        return True
    # Begun outside the hours: they overlap only if the hours begin during the run.
    opens = datetime.combine(started.date(), start)
    return (opens if opens >= started else opens + timedelta(days=1)) <= ended


class QueueEndDialog(QDialog):
    """The "Still watching?" dialog: how many of the run you watched, answered by
    None · First only · All (Enter = All), and a link to when it is asked. The
    answer is :attr:`choice` (``None`` when closed without one). Its answers are
    methods, not lambdas: a lambda holding the dialog would keep it alive."""

    def __init__(self, parent, count: int, navigate):
        super().__init__(parent)
        self.choice = None
        ep_label = "1 more episode" if count == 1 else f"{count} more episodes"
        self.setWindowTitle("Still watching?")
        self.setModal(True)
        self.setMinimumWidth(PROMPT_MIN_WIDTH)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        msg = QLabel(f"The queue played {ep_label} after the one you started.\n\nHow many did you watch?")
        msg.setWordWrap(True)
        layout.addWidget(msg)

        to_setting = QLabel(f'<a href="{PROMPT_SETTING_LINK}">Change when this is asked</a>')
        to_setting.setToolTip("Open Settings at the option that says when this question is asked")
        to_setting.linkActivated.connect(navigate)
        layout.addWidget(to_setting)

        # Added in reading order, least to most watched; All is the default (Enter), as Yes was.
        btns = dialog_buttons(self, ok=None, cancel=False, extra=(
            ("None", self._none), ("First only", self._first_only), ("All", self._all)))
        action_button(btns, "All").setDefault(True)
        btns.setToolTip("None: the first episode and the rest go back to unwatched · First only: "
                        "keep the first, the rest go back · All: keep them all")
        layout.addWidget(btns)
        self.adjustSize()

    def _answer(self, choice: str) -> None:
        self.choice = choice
        self.accept()

    def _none(self) -> None:
        self._answer(NONE)

    def _first_only(self) -> None:
        self._answer(FIRST_ONLY)

    def _all(self) -> None:
        self._answer(ALL)


def build_queue_end_dialog(parent, count: int, navigate) -> QueueEndDialog:
    """The "Still watching?" dialog for a run that played on ``count`` episodes."""
    return QueueEndDialog(parent, count, navigate)


class _QueueEndPromptMixin:
    """"Still watching?" prompt + the answers' persistence paths."""

    def _on_queue_end_detected(self, auto_episode_ids: list, first_episode_id: str = "") -> None:
        """Main-thread slot: ask how many of a queue run were watched.

        Called when the ``_queue_end_detected`` signal fires (emitted from the
        off-thread checkpoint tick after a queued player window closes with
        ``last_seen_pos > 0``, when ``asks_now`` says so).

        Args:
            auto_episode_ids: Episode DB ids that were auto-advanced (played via
                ``'queue'``). These are episodes at queue indices 1‥last_seen_pos.
                Index 0 is already ``'manual'`` (the user explicitly started it).
            first_episode_id: That index-0 episode; "None" takes it back too (the
                viewer fell asleep during it, owner 2026-11-22).
        """
        if not auto_episode_ids:
            return
        if not getattr(self.config, "prompt_after_autoplay", True):
            return

        dlg = build_queue_end_dialog(self, len(auto_episode_ids), lambda link: self.navigate_to(link))
        dlg.exec()
        choice = dlg.choice
        if choice == ALL:
            # Promote to 'manual' so they render solid and the resume anchor advances.
            self.executor.submit(self._bg_promote_queue_episodes, auto_episode_ids)
        elif choice in (FIRST_ONLY, NONE):
            # The queue marked them watched while nobody was watching: take it back.
            self.executor.submit(self._bg_unmark_queue_episodes, auto_episode_ids)
            if choice == NONE and first_episode_id:
                self.executor.submit(self._bg_unmark_first_episode, first_episode_id)

    def _bg_unmark_first_episode(self, episode_id: str) -> None:
        """Worker: the viewer did not watch the episode the run started with.

        It was written complete when the playlist moved past it, so take that back.
        Only a completed episode is touched; anything else has no mark to undo.
        """
        try:
            with self.db.session_scope() as session:
                repos = RepositoryFactory(session)
                ep = repos.episodes.get_by_id(episode_id)
                if ep is not None and ep.watch_completed:
                    repos.episodes.mark_watched_bulk([episode_id], False, forget_play=True)
                    logger.info("Unmarked the run's first episode — the viewer did not watch it")
        except Exception as exc:
            logger.warning(f"Failed to unmark the run's first episode: {exc}")
        self._episode_watch_state_changed.emit([episode_id])

    def _bg_promote_queue_episodes(self, episode_ids: list) -> None:
        """Worker: flip ``last_played_via`` to ``'manual'`` for confirmed episodes.

        Runs off the main thread.  Uses ``mark_episodes_as_engaged`` from the
        episode repository — a thin bulk updater that commits once.

        Args:
            episode_ids: DB ids of the episodes to promote.
        """
        try:
            with self.db.session_scope() as session:
                repos = RepositoryFactory(session)
                updated = repos.episodes.mark_episodes_as_engaged(episode_ids)
                logger.info(
                    f"Promoted {updated}/{len(episode_ids)} queue-watched episode(s) "
                    "to manual engagement after user confirmation"
                )
        except Exception as exc:
            logger.warning(f"Failed to promote queue-watched episodes: {exc}")
        self._episode_watch_state_changed.emit(list(episode_ids))

    def _bg_unmark_queue_episodes(self, episode_ids: list) -> None:
        """Worker: undo the auto-mark for episodes the user says they did not watch.

        The queue path writes each auto-advanced episode 100%-complete as the
        playlist moves past it, so answering "No" has to actively clear that —
        the same coherent field write the context menu's "Mark unwatched" makes,
        through the same repository chokepoint.

        QUEUE-1: "No" must take back only what the QUEUE itself marked — an
        episode still in progress (a saved resume position, never completed)
        or never played has nothing the queue wrote, so clearing it would
        erase a real position rather than undo an auto-mark.

        Args:
            episode_ids: DB ids of the episodes to unmark.
        """
        try:
            with self.db.session_scope() as session:
                repos = RepositoryFactory(session)
                to_clear = []
                skipped = 0
                for episode_id in episode_ids:
                    ep = repos.episodes.get_by_id(episode_id)
                    if ep is not None and ep.watch_completed and ep.last_played_via == "queue":
                        to_clear.append(episode_id)
                    else:
                        skipped += 1
                updated = repos.episodes.mark_watched_bulk(to_clear, False, forget_play=True)
                logger.info(
                    f"Unmarked {updated}/{len(to_clear)} queue-watched episode(s) — "
                    "user answered No to the queue-end prompt"
                )
                if skipped:
                    logger.info(f"{skipped} left alone: not marked by the queue")
        except Exception as exc:
            logger.warning(f"Failed to unmark queue-watched episodes: {exc}")
        self._episode_watch_state_changed.emit(list(episode_ids))
