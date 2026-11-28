"""Discover cards show your judgment of a title and offer Watch Later in one click.

Owner (2026-11-28): a title you rated shows it (like, dislike, not interested), so
you can see what you've already decided on; hovering a poster shows a Watch Later
button, and the queued icon itself is clickable.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QApplication, QLabel

from streamselect.core.config import Config
from streamselect.core.discovery_engine import ContentCard


def _card(**kw):
    base = {"channel_id": "c1", "title": "Heat", "media_type": "movie", "thumbnail_url": None, "rating": 7.0,
                "year": 1995, "genre": "Crime"}
    return ContentCard(**{**base, **kw})


def test_a_judgment_belongs_to_the_title_across_its_copies(tmp_path):
    from streamselect.core.card_judgments import with_judgments
    from streamselect.core.database import ChannelDB, Database, ProviderDB, UserRatingDB

    db = Database(f"sqlite:///{tmp_path / 'j.db'}")
    db.create_tables()
    with db.session_scope() as s:
        s.add(ProviderDB(id="p1", name="P", type="xtream", url="http://x.example.com", is_active=True))
        for cid, key in (("a1", "heat|movie"), ("a2", "heat|movie"), ("b1", "ronin|movie"), ("n1", "nope|movie")):
            s.add(ChannelDB(id=cid, source_id=cid, provider_id="p1", name=cid, media_type="movie",
                            content_key=key, is_rec_suppressed=(cid == "n1")))
        s.add(UserRatingDB(channel_id="a2", rating=-1))     # disliked under the OTHER copy
        s.add(UserRatingDB(channel_id="b1", rating=1))
    cards = [_card(channel_id="a1", content_key="heat|movie"), _card(channel_id="b1", content_key="ronin|movie"),
             _card(channel_id="n1", content_key="nope|movie"), _card(channel_id="z", content_key="other|movie")]
    with db.session_scope(commit=False) as s:
        out = with_judgments(s, cards)
    assert [(c.user_rating, c.is_rec_suppressed) for c in out] == [(-1, False), (1, False), (0, True), (0, False)]
    assert out[1].is_liked


@pytest.fixture()
def make(qapp, owned_widgets, tmp_path):
    from streamselect.gui.discover_card import _ContentCard

    def build(**kw):
        w = owned_widgets.own(_ContentCard(_card(**kw), MagicMock(), Config(config_dir=tmp_path)))
        w.show()
        QApplication.processEvents()
        return w
    return build


@pytest.mark.parametrize("kw, role", [({"user_rating": -1}, "dislike"), ({"is_rec_suppressed": True}, "not_interested"),
                                      ({"user_rating": 1}, "like")])
def test_your_judgment_shows_on_the_card(make, kw, role):
    from streamselect.gui import icon_utils
    w = make(**kw)
    labels = [lbl.text() for lbl in w.findChildren(QLabel)]
    assert any(icon_utils.role_html(role) in t for t in labels), f"{role} badge on the poster"


def test_the_watch_later_button_shows_when_queued_or_hovered_and_toggles(make):
    from PyQt6.QtCore import QEvent, QPointF
    from PyQt6.QtGui import QEnterEvent

    queued = make(in_queue=True)
    assert queued._queue_btn.isVisible() and queued._queue_btn.toolTip() == "Remove from Watch Later"
    plain = make()
    assert not plain._queue_btn.isVisible()
    got = []
    plain.queueToggleRequested.connect(got.append)
    QApplication.sendEvent(plain, QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))
    assert plain._queue_btn.isVisible(), "appears on hover"
    plain._queue_btn.click()
    assert got == ["c1"]
    QApplication.sendEvent(plain, QEvent(QEvent.Type.Leave))
    assert not plain._queue_btn.isVisible()


def test_no_button_where_nothing_listens(make):
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QEnterEvent

    w = make()                               # e.g. Recipe's cards, not wired to the queue
    QApplication.sendEvent(w, QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))
    assert not w._queue_btn.isVisible()


def test_a_rating_made_elsewhere_reaches_the_card(qapp):
    from dataclasses import replace

    from streamselect.gui.channel_state_bus import row_changes
    c = _card()
    assert replace(c, **row_changes({"rating": -1}, c)).user_rating == -1
    assert replace(c, **row_changes({"is_suppressed": True}, c)).is_rec_suppressed
