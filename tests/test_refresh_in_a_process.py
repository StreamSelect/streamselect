"""A source refresh runs in its own process, so its memory goes back when it ends.

Measured 2026-11-16: one live-channel refresh run in-thread left the app
~260 MB larger for good, with only ~30 MB still in use. These tests prove the
refresh works across the process boundary: the worker's protocol, a real
spawned child, and the window's handle on a child that dies.
"""

from __future__ import annotations

import multiprocessing
from types import SimpleNamespace

import pytest

from streamselect.core import refresh_worker
from streamselect.core.database import ChannelDB, Database, ProviderDB
from streamselect.gui.provider_load_process import ProviderLoadProcess
from tests.conftest import make_channel_double

PID = "prov-refresh-proc"


@pytest.fixture
def db(tmp_path):
    database = Database(f"sqlite:///{tmp_path / 'refresh.db'}")
    database.create_tables()
    with database.session_scope() as s:
        s.add(ProviderDB(id=PID, name="One source", type="xtream", url="http://example.com",
                         username="u", password="p", is_active=True))
    yield database
    database.engine.dispose()


def _request(db, tmp_path, kind="live_only"):
    return refresh_worker.build_request(PID, str(db.engine.url), kind, {})


def test_the_worker_refreshes_and_reports_progress_then_one_result(db, tmp_path, monkeypatch):
    """The child's whole job, run in-process: the loader stores the channels and the
    window hears progress, then exactly one result, last."""
    from streamselect.core import app_logging, provider_loader

    monkeypatch.setattr(app_logging, "configure_logging", lambda *_a, **_k: None)

    class _Plugin:
        async def fetch_channels(self, provider, progress_callback=None, media_types=None):
            progress_callback(1, 1, "Fetched")
            return [make_channel_double(id=f"{PID}_1", source_id="1", provider_id=PID, name="News One",
                                        media_type="live")]

    monkeypatch.setattr(provider_loader, "get_provider", lambda _type: _Plugin())
    receive, send = multiprocessing.Pipe(duplex=False)
    refresh_worker.run_refresh(_request(db, tmp_path), send)

    messages = []
    try:
        while True:
            messages.append(receive.recv())
    except EOFError:                                  # the worker closed its end
        pass
    assert [m[0] for m in messages][-1] == "finished" and [m[0] for m in messages].count("finished") == 1
    assert any(m[0] == "progress" for m in messages)
    _tag, ok, text, _stats = messages[-1]
    assert ok, text
    with db.session_scope() as s:
        assert s.query(ChannelDB).filter_by(provider_id=PID).count() == 1


def test_a_missing_source_is_reported_not_raised(db, tmp_path, monkeypatch):
    from streamselect.core import app_logging

    monkeypatch.setattr(app_logging, "configure_logging", lambda *_a, **_k: None)
    request = refresh_worker.build_request("nobody", str(db.engine.url), "full", {})
    receive, send = multiprocessing.Pipe(duplex=False)
    refresh_worker.run_refresh(request, send)
    assert receive.recv() == ("finished", False, "Provider not found", None)


def test_a_real_child_process_reports_back_to_the_window(qtbot, db, tmp_path):
    """Spawn, pipe and poll for real: a child for a source that does not exist
    exits at once, and the window hears why. Nothing touches the network."""
    loader = ProviderLoadProcess(SimpleNamespace(id="nobody"), db, kind="full")
    with qtbot.waitSignal(loader.finished, timeout=60_000) as got:
        loader.start()
    assert got.args == [False, "Provider not found"]
    assert not loader.isRunning()


def test_a_child_that_dies_without_a_word_still_ends_the_refresh(qapp, db):
    loader = ProviderLoadProcess(SimpleNamespace(id=PID), db)
    ended = []
    loader.finished.connect(lambda ok, text: ended.append((ok, text)))
    receive, send = multiprocessing.Pipe(duplex=False)
    send.close()                                      # the child is gone
    loader._conn = receive
    loader._proc = SimpleNamespace(is_alive=lambda: False, exitcode=-9, join=lambda _t: None)
    loader._poll()
    assert ended and ended[0][0] is False and "-9" in ended[0][1]
    loader._poll()
    assert len(ended) == 1, "the end is reported once"
