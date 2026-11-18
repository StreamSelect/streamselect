"""Watch Queue: swap items on unusable sources for the same title on an active one.

Owner, 2026-11-17: list them as [queued copy] -> [copy on an active source], let
the user untick, keep no-match items, carry watch history over, offer Undo.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from PyQt6.QtCore import Qt

from streamselect.core.database import ChannelDB, ProviderDB, WatchQueueDB
from streamselect.core.queue_replacement import (
    SCOPE_ALL, SCOPE_EXPIRED, find_stranded, replace, undo,
)
from streamselect.core.repositories import RepositoryFactory

T0 = datetime(2026, 11, 1, 20, 0)


def _seed(db):
    """Source "old" expired, "off" switched off, "live" usable."""
    with db.session_scope() as s:
        s.add(ProviderDB(id="old", name="Old Source", type="xtream", url="http://example.com",
                         is_active=True, account_exp_date=datetime.now() - timedelta(days=3)))
        s.add(ProviderDB(id="off", name="Off Source", type="xtream", url="http://example.com",
                         is_active=False))
        s.add(ProviderDB(id="live", name="Live Source", type="xtream", url="http://example.com",
                         is_active=True))

        def ch(cid, pid, name, key, prefix="EN", **kw):
            s.add(ChannelDB(id=cid, source_id=cid, provider_id=pid, name=name, media_type="movie",
                            content_key=key, detected_prefix=prefix, detected_title=name, **kw))
        ch("old_1", "old", "Dark Matter", "tmdb:1|movie", last_played=T0, play_count=2,
           watch_progress=1800, watch_percent=40, last_played_via="queue")
        ch("live_1", "live", "Dark Matter", "tmdb:1|movie", detected_quality="4K")
        ch("live_1de", "live", "Dark Matter", "tmdb:1|movie", prefix="DE")
        ch("old_2", "old", "Paper Moon", "tmdb:2|movie")                       # no copy anywhere
        ch("old_3", "old", "Heat", "tmdb:3|movie", prefix="SW")
        ch("live_3", "live", "Heat", "tmdb:3|movie", prefix="D+")             # only another language
        ch("off_4", "off", "Arrival", "tmdb:4|movie")
        ch("live_4", "live", "Arrival", "tmdb:4|movie")
        ch("old_5", "old", "Ronin", "tmdb:5|movie")
        ch("live_5", "live", "Ronin", "tmdb:5|movie")                           # already queued itself
        ch("old_7", "old", "Alien: Earth", "tmdb:7|movie")          # queued from live already...
        ch("live_7a", "live", "Alien: Earth", "tmdb:7|movie")
        ch("live_7b", "live", "Alien: Earth", "tmdb:7|movie")       # ...though this copy is free
        ch("old_6", "old", "Kiss TV", "kiss tv|live")                # matched by name only
        ch("live_6", "live", "Kiss TV", "kiss tv|live")
        for pos, cid in enumerate(["old_1", "old_2", "old_3", "off_4", "old_5", "live_5", "old_6",
                                   "old_7", "live_7a"]):
            s.add(WatchQueueDB(channel_id=cid, channel_name=cid, media_type="movie",
                               source_id=cid, position=pos, added_at=T0 + timedelta(minutes=pos)))


def _scan(db, scope=SCOPE_ALL):
    with db.session_scope(commit=False) as s:
        return {x.old.channel_id: x for x in find_stranded(RepositoryFactory(s), scope)}


def test_items_on_unusable_sources_are_found_with_their_copies_language_first(db):
    _seed(db)
    found = _scan(db)
    assert set(found) == {"old_1", "old_2", "old_3", "off_4", "old_5", "old_6", "old_7"}, \
        "active untouched"
    assert found["old_1"].doubts == ()
    assert found["old_3"].doubts == ("different language: SW → D+",)
    assert found["old_6"].doubts == ("matched by name only",)
    assert [c.channel_id for c in found["old_1"].candidates] == ["live_1", "live_1de"]
    assert found["old_1"].best.same_language
    assert found["old_2"].best is None and "No copy" in found["old_2"].reason
    assert not found["old_3"].best.same_language, "only another language is on offer"
    assert found["old_5"].best is None and found["old_5"].duplicate
    assert found["old_5"].reason == "Already in your queue from Live Source"
    assert found["old_7"].duplicate and found["old_7"].best is None, \
        "another free copy would still queue the title twice"
    assert found["off_4"].state == "disabled" and found["old_1"].state == "expired"


def test_an_item_on_a_deleted_source_names_it_in_words_not_by_its_id(db):
    from streamselect.core.queue_replacement import REMOVED_SOURCE
    _seed(db)
    with db.session_scope() as s:
        s.add(ChannelDB(id="gone_8", source_id="gone_8", provider_id="deleted-source-id",
                        name="Heat", media_type="movie", content_key="tmdb:3|movie",
                        detected_prefix="SW", detected_title="Heat"))
        s.add(WatchQueueDB(channel_id="gone_8", channel_name="Heat", media_type="movie",
                           source_id="gone_8", position=99))
    found = _scan(db)["gone_8"]
    assert found.state == "removed" and found.old.source == REMOVED_SOURCE
    assert set(_scan(db, SCOPE_EXPIRED)) == {"old_1", "old_2", "old_3", "old_5", "old_6", "old_7"}


def test_a_swap_keeps_the_place_moves_the_history_and_undo_puts_it_back(db):
    _seed(db)
    with db.session_scope(commit=False) as s:
        before = {r.id: (r.position, r.added_at) for r in s.query(WatchQueueDB)}
        qid = s.query(WatchQueueDB.id).filter_by(channel_id="old_1").scalar()
    with db.session_scope() as s:
        out = replace(s, [(qid, "live_1")])
    assert (out.replaced, out.skipped) == (1, 0)
    snap = out.snapshot
    with db.session_scope(commit=False) as s:
        row = s.get(WatchQueueDB, qid)
        assert row.channel_id == "live_1" and (row.position, row.added_at) == before[qid]
        new, old = s.get(ChannelDB, "live_1"), s.get(ChannelDB, "old_1")
        assert (new.last_played, new.play_count, new.watch_progress, new.watch_percent,
                new.last_played_via) == (T0, 2, 1800, 40, "queue")
        assert old.last_played is None and old.play_count == 0, "moved, not copied"
    with db.session_scope() as s:
        assert undo(s, snap) == 1
    with db.session_scope(commit=False) as s:
        assert s.get(WatchQueueDB, qid).channel_id == "old_1"
        old, new = s.get(ChannelDB, "old_1"), s.get(ChannelDB, "live_1")
        assert (old.last_played, old.play_count, old.watch_progress) == (T0, 2, 1800)
        assert new.last_played is None and not new.play_count


def test_a_copy_already_queued_is_never_made_a_duplicate(db):
    _seed(db)
    with db.session_scope(commit=False) as s:
        ids = dict(s.query(WatchQueueDB.channel_id, WatchQueueDB.id))
    with db.session_scope() as s:
        out = replace(s, [(ids["old_1"], "live_1"), (ids["old_5"], "live_5")])
    assert (out.replaced, out.skipped) == (1, 1)
    with db.session_scope(commit=False) as s:
        assert s.query(WatchQueueDB).filter_by(channel_id="live_5").count() == 1


def _dialog(db, qapp, owned_widgets):
    from streamselect.gui.queue_replace_dialog import QueueReplaceDialog
    with db.session_scope(commit=False) as s:
        stranded = find_stranded(RepositoryFactory(s), SCOPE_ALL)
    dlg = owned_widgets.own(QueueReplaceDialog(stranded))
    dlg.show()
    qapp.processEvents()
    rows = {s.old.channel_id: item for s, item, _c in dlg._rows}
    return dlg, rows


def test_the_window_shows_queued_copy_then_its_replacement_grouped_by_confidence(
        db, qapp, owned_widgets):
    from streamselect.gui.queue_replace_dialog import (
        COL_NEW, COL_NOTE, COL_OLD, GROUP_CHECK, GROUP_DUPLICATE, GROUP_NONE, GROUP_SURE,
    )
    _seed(db)
    dlg, rows = _dialog(db, qapp, owned_widgets)
    assert set(rows) == {"old_1", "old_2", "old_3", "old_5", "old_6", "old_7"}, "expired only"
    assert rows["old_7"].parent() is dlg.groups[GROUP_DUPLICATE]
    assert rows["old_6"].parent() is dlg.groups[GROUP_CHECK]
    assert rows["old_6"].text(COL_NOTE) == "Matched by name only"

    one = rows["old_1"]
    assert one.parent() is dlg.groups[GROUP_SURE]
    assert one.text(COL_OLD).startswith("EN · Dark Matter") and "Old Source · expired" in one.text(COL_OLD)
    combo = dlg.tree.itemWidget(one, COL_NEW)
    assert combo is not None and combo.currentText() == "EN · Dark Matter · 4K · Live Source"
    old_rect, new_rect = dlg.tree.visualItemRect(one), combo.geometry()
    assert dlg.tree.columnViewportPosition(COL_OLD) < new_rect.x(), "queued copy left, new copy right"
    assert abs(new_rect.center().y() - old_rect.center().y()) <= 2, "on one line"
    assert one.checkState(COL_OLD) == Qt.CheckState.Checked

    doubt = rows["old_3"]
    assert doubt.parent() is dlg.groups[GROUP_CHECK]
    assert doubt.checkState(COL_OLD) == Qt.CheckState.Unchecked
    assert doubt.text(COL_NOTE) == "Different language: SW → D+"
    check_y = dlg.tree.visualItemRect(dlg.groups[GROUP_CHECK]).y()
    assert dlg.tree.visualItemRect(dlg.groups[GROUP_SURE]).y() < check_y, "sure swaps first"

    none = rows["old_2"]
    assert none.parent() is dlg.groups[GROUP_NONE]
    assert not none.flags() & Qt.ItemFlag.ItemIsEnabled and "No copy" in none.text(COL_NOTE)
    assert not none.flags() & Qt.ItemFlag.ItemIsUserCheckable
    assert dlg._ok.text() == "Replace 1"

    dlg.groups[GROUP_CHECK].setCheckState(COL_OLD, Qt.CheckState.Checked)   # tick the group
    assert doubt.checkState(COL_OLD) == Qt.CheckState.Checked
    assert dlg._ok.text() == "Replace 3"
    combo.setCurrentIndex(1)
    assert sorted(cid for _q, cid in dlg.choices()) == ["live_1de", "live_3", "live_6"]
    dlg.groups[GROUP_SURE].setCheckState(COL_OLD, Qt.CheckState.Unchecked)
    assert sorted(cid for _q, cid in dlg.choices()) == ["live_3", "live_6"]
    dlg.everything.setChecked(True)
    qapp.processEvents()
    assert "off_4" in {s.old.channel_id for s, _i, _c in dlg._rows}


def test_replacing_from_the_window_offers_undo(db, qapp, owned_widgets):
    from streamselect.gui import queue_replace_dialog as qrd

    _seed(db)
    toasts, statuses, refreshed = [], [], []

    class Host:
        def __init__(self):
            self.db = db
            self.notification_manager = self
            self.load_history = lambda: refreshed.append("history")

        def show(self, **kw):
            toasts.append(kw)

        def status(self, text, **_kw):
            statuses.append(text)

    class Section:
        def refresh(self):
            refreshed.append("queue")

    with db.session_scope(commit=False) as s:
        qid = s.query(WatchQueueDB.id).filter_by(channel_id="old_1").scalar()
    host, section = Host(), Section()
    qrd.apply_replacements(host, section, [(qid, "live_1")])
    assert refreshed == ["queue", "history"]
    (label, undo_fn), = toasts[-1]["actions"]
    assert label == "Undo"
    undo_fn()
    with db.session_scope(commit=False) as s:
        assert s.get(WatchQueueDB, qid).channel_id == "old_1"
    assert statuses[-1] == "Put back 1 queue item(s)"


def test_replace_keeps_the_window_open_and_the_doubtful_rows_move_up(
        db, qapp, owned_widgets, monkeypatch):
    """Owner: commit the sure section, it clears, and the less sure shift up."""
    from streamselect.gui import queue_replace_dialog as qrd
    from streamselect.gui.queue_replace_dialog import GROUP_CHECK, GROUP_SURE

    _seed(db)
    opened, toasts = [], []

    def run_query(fn, on_result, **_kw):
        with db.session_scope(commit=False) as s:
            on_result(fn(RepositoryFactory(s)))

    from PyQt6.QtWidgets import QWidget

    class Host(QWidget):
        config = None

        def __init__(self):
            super().__init__()
            self.db, self._run_query, self.notification_manager = db, run_query, self
            self.load_history = lambda: None

        def show(self, **kw):
            toasts.append(kw)

        def status(self, *_a, **_kw):
            pass

    class Section:
        def refresh(self):
            pass

    def fake_exec(dialog):
        opened.append(owned_widgets.own(dialog))
        dialog.show()
        return 0

    monkeypatch.setattr(qrd.QueueReplaceDialog, "exec", fake_exec)
    qrd.open_queue_replace(owned_widgets.own(Host()), Section())
    (dlg,) = opened
    assert GROUP_SURE in dlg.groups
    dlg._ok.click()                                    # Replace the ticked (sure) rows
    qapp.processEvents()
    assert dlg.isVisible(), "the window stays open"
    assert GROUP_SURE not in dlg.groups, "the sure rows are done and gone"
    assert dlg.tree.topLevelItem(0) is dlg.groups[GROUP_CHECK], "the doubtful rows are on top"
    assert dlg._ok.text() == "Replace" and not dlg._ok.isEnabled()
    (label, undo_fn), = toasts[-1]["actions"]
    undo_fn()
    qapp.processEvents()
    assert dlg.tree.topLevelItem(0) is dlg.groups[GROUP_SURE], "Undo brings them back"


def test_a_struck_item_is_removed_not_migrated_and_undo_puts_it_back_in_place(db):
    _seed(db)
    with db.session_scope(commit=False) as s:
        row = s.query(WatchQueueDB).filter_by(channel_id="old_2").one()
        before = (row.id, row.position, row.added_at)
    with db.session_scope() as s:
        out = replace(s, [], [before[0]])
    assert (out.replaced, out.removed) == (0, 1)
    with db.session_scope(commit=False) as s:
        assert s.get(WatchQueueDB, before[0]) is None
    with db.session_scope() as s:
        assert undo(s, out.snapshot) == 1
    with db.session_scope(commit=False) as s:
        row = s.get(WatchQueueDB, before[0])
        assert (row.id, row.position, row.added_at, row.channel_id) == (*before, "old_2")


def test_the_trash_button_strikes_a_row_through_and_turns_it_into_a_removal(
        db, qapp, owned_widgets):
    from streamselect.gui.queue_replace_dialog import (
        COL_NEW, COL_NOTE, COL_OLD, COL_REMOVE, GROUP_DUPLICATE, REMOVING_NOTE,
    )
    _seed(db)
    dlg, rows = _dialog(db, qapp, owned_widgets)
    ids = {s.old.channel_id: s.queue_id for s, _i, _c in dlg._rows}
    one, dupe = rows["old_1"], rows["old_7"]
    trash, cell = dlg._trash_of[id(one)], dlg.tree.itemWidget(one, COL_REMOVE)
    combo = dlg.tree.itemWidget(one, COL_NEW)
    assert cell.geometry().x() > combo.geometry().right(), "the trash button is at the far right"
    assert abs(cell.geometry().center().y() - dlg.tree.visualItemRect(one).center().y()) <= 2

    trash.click()
    assert one.font(COL_OLD).strikeOut() and combo.font().strikeOut() and not combo.isEnabled()
    assert one.text(COL_NOTE) == REMOVING_NOTE
    assert one.checkState(COL_OLD) == Qt.CheckState.Unchecked
    assert dlg.removals() == [ids["old_1"]] and dlg.choices() == []
    assert dlg._ok.text() == "Remove 1" and dlg._ok.isEnabled()

    dlg._trash_of[id(dlg.groups[GROUP_DUPLICATE])].click()          # the whole group
    assert dupe.font(COL_OLD).strikeOut()
    assert sorted(dlg.removals()) == sorted([ids["old_1"], ids["old_5"], ids["old_7"]])

    trash.click()                                                   # keep it after all
    assert not one.font(COL_OLD).strikeOut() and combo.isEnabled()
    assert one.text(COL_NOTE) == ""
    one.setCheckState(COL_OLD, Qt.CheckState.Checked)
    assert dlg._ok.text() == "Replace 1 · Remove 2"


def test_only_the_row_under_the_mouse_shows_its_trash_and_a_highlight(db, qapp, owned_widgets):
    """Owner: a trash button on every row is "a messy row of trash"; show it on
    the hovered row, lightly highlighted. A struck row keeps its button to undo."""
    from PyQt6.QtCore import QEvent, QPointF
    from PyQt6.QtGui import QMouseEvent

    from streamselect.gui.queue_replace_dialog import COL_NOTE, COL_OLD
    _seed(db)
    dlg, rows = _dialog(db, qapp, owned_widgets)
    a, b = rows["old_1"], rows["old_2"]
    trash_a, trash_b = (dlg._trash_of[id(r)] for r in (a, b))
    assert not trash_a.isVisible() and not trash_b.isVisible(), "no trash until hovered"

    def hover(item):
        at = QPointF(dlg.tree.visualItemRect(item).center()) + QPointF(0, 0)
        at.setX(5)
        ev = QMouseEvent(QEvent.Type.MouseMove, at, at, Qt.MouseButton.NoButton,
                         Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        qapp.sendEvent(dlg.tree.viewport(), ev)
        qapp.processEvents()

    hover(a)
    assert trash_a.isVisible() and not trash_b.isVisible()
    assert a.background(COL_OLD).style() != Qt.BrushStyle.NoBrush
    assert a.background(COL_NOTE).color() == a.background(COL_OLD).color(), "the whole row"
    assert b.background(COL_OLD).style() == Qt.BrushStyle.NoBrush
    hover(b)
    assert trash_b.isVisible() and not trash_a.isVisible(), "it goes when the mouse moves on"
    hover(a)
    trash_a.click()                                  # strike it
    hover(b)
    assert trash_b.isVisible() and trash_a.isVisible(), "a struck row keeps its button"
    assert a.background(COL_OLD).style() == Qt.BrushStyle.NoBrush, "highlight followed the mouse"
