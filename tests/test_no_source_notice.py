"""A persistent notice whenever there is no source to read from (user report, Q3/R5).

Bottom right, no timeout, closable, an action on its second row. It appears at
launch and the moment the last source is removed, expires or is turned off, and
is worded by cause. A notice the user closed stays closed while the cause is
the same.
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timedelta

import pytest
from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QLabel, QPushButton

from streamselect.core.database import ProviderDB
from streamselect.core.repositories.dtos import SourceAvailability
from streamselect.gui.empty_state import no_source_notice_text
from streamselect.gui.main_window_empty_state import _EmptyStateMixin
from streamselect.gui.main_window_source_add import _SourceAddMixin


def _a(total, usable=0, off=0, expired=0, last=None) -> SourceAvailability:
    return SourceAvailability(total=total, usable=usable, turned_off=off,
                              expired=expired, last_expired_at=last)


@pytest.mark.parametrize(("avail", "title", "action"), [
    (_a(0), "No sources available", "add"),
    (_a(1, off=1), "Your source is turned off", "open"),
    (_a(3, off=3), "All 3 sources are turned off", "open"),
    (_a(1, expired=1, last=datetime(2026, 3, 14)), "Your source expired on", "open"),
    (_a(2, expired=2), "All 2 sources have expired", "open"),
    (_a(2, off=1, expired=1), "No source is usable", "open"),
])
def test_the_notice_names_the_cause(avail, title, action):
    text = no_source_notice_text(avail)
    assert text is not None and text[0].startswith(title)
    assert text[2] == action


def test_a_usable_source_means_no_notice():
    assert no_source_notice_text(_a(4, usable=1, off=2, expired=1)) is None


class _Host(_SourceAddMixin, _EmptyStateMixin, QObject):
    """The real mixin on a QObject: nothing of it is copied, so nothing goes stale."""

    def __init__(self, db):
        from streamselect.core.notifications import NotificationManager
        super().__init__()
        self.db = db
        self.notification_manager = NotificationManager()
        self.opened = 0

    def switch_to_sources_manager(self):
        self.opened += 1

    def _refresh_provider_dependent_views(self):
        self._sync_no_source_notice()


def _titles(host):
    return [n.title for n in host.notification_manager.get_visible_notifications()]


def _add(db, pid, **kw):
    with db.session_scope() as s:
        s.add(ProviderDB(id=pid, name=pid, type="xtream", url=f"http://{pid}", urls=[],
                         username="u", password="p", **kw))


def test_the_notice_follows_the_sources(qapp, db):
    host = _Host(db)
    host._sync_no_source_notice()
    assert _titles(host) == ["No sources available"]
    note = host.notification_manager.get_visible_notifications()[0]
    assert note.auto_dismiss_seconds is None and note.dismissible, "persistent, but closable"

    _add(db, "a", is_active=False)
    host._sync_no_source_notice()
    assert _titles(host) == ["Your source is turned off"], "re-worded, never stacked"

    with db.session_scope() as s:
        s.get(ProviderDB, "a").is_active = True
    host._sync_no_source_notice()
    assert _titles(host) == [], "a usable source closes the notice"

    with db.session_scope() as s:
        s.get(ProviderDB, "a").account_exp_date = datetime.now() - timedelta(days=1)
    host._sync_no_source_notice()
    assert _titles(host)[0].startswith("Your source expired on")
    host.notification_manager.get_visible_notifications()[0].actions[0][1]()
    assert host.opened == 1, "Open Sources goes to the Sources screen"


def test_a_closed_notice_stays_closed_until_the_cause_changes(qapp, db):
    host = _Host(db)
    host._sync_no_source_notice()
    host.notification_manager.dismiss(host._no_source_notice[1])
    host._sync_no_source_notice()
    assert _titles(host) == [], "the user closed it; the same cause must not nag"

    _add(db, "a", is_active=False)
    host._sync_no_source_notice()
    assert _titles(host) == ["Your source is turned off"], "a new cause shows it again"


def test_the_last_source_expiring_shows_the_notice_without_any_other_event(qapp, db):
    """'The moment it expires' — nothing else happens at that moment, so a timer must."""
    import time

    _add(db, "a", account_exp_date=datetime.now() + timedelta(seconds=1))
    host = _Host(db)
    host._sync_no_source_notice()
    assert _titles(host) == []
    end = time.time() + 5
    while not _titles(host) and time.time() < end:
        qapp.processEvents()
        time.sleep(0.05)
    assert _titles(host) and _titles(host)[0].startswith("Your source expired on")


def test_the_action_sits_on_its_own_row_below_the_message(qapp, owned_widgets):
    """R5's sketch: the button on the second row, not squeezed beside the text."""
    from streamselect.core.config import Config
    from streamselect.core.notifications import Notification, NotificationType
    from streamselect.gui.notification_widget import NotificationCard

    title, message, _ = no_source_notice_text(_a(0))
    card = owned_widgets.own(NotificationCard(
        Notification(title=title, message=message, type=NotificationType.WARNING,
                     actions=[("Add Source", lambda: None)]),
        Config(config_dir=tempfile.mkdtemp())))
    card.resize(340, card.sizeHint().height())
    card.show()
    qapp.processEvents()
    msg = next(lb for lb in card.findChildren(QLabel) if message in lb.text())
    btn = next(b for b in card.findChildren(QPushButton) if b.text() == "Add Source")
    msg_bottom = msg.mapTo(card, msg.rect().bottomLeft()).y()
    btn_top = btn.mapTo(card, btn.rect().topLeft()).y()
    assert btn_top >= msg_bottom, "the button must sit below the message"
    assert btn.width() >= btn.sizeHint().width(), "the button's label is cut"
