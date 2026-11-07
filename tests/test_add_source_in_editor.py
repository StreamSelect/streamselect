"""Adding a source happens in the Sources editor, and a failed test never sticks.

a user, on the macOS build: a source with a wrong username/password failed
its test (correctly), but after the credentials were corrected the dialog kept
failing instantly until the app was relaunched. ``AddProviderDialog`` is gone —
every Add Source button now opens the editor on a blank source — so the
sequence that must work is this one, driven on the real editor against a real
local server (CI runs it on macOS as well as Linux):

    wrong credentials -> test fails, Add stays disabled
    right credentials -> test passes, Add enables
    Add               -> the source exists, with what was on the form

A hostname, not 127.0.0.1, so name resolution runs as it does for a provider.
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, quote, urlparse

import pytest

from streamselect.core.database import ProviderDB

GOOD_PASSWORD = "p&ss#1+ok"   # characters that break an unescaped query string


class _Xtream(BaseHTTPRequestHandler):
    #: Set by a test to answer every request 403, as a provider does while it
    #: has locked the caller out after failed logins.
    locked_out = False

    def log_message(self, *_a):  # quiet
        pass

    def do_GET(self):  # noqa: N802 (http.server API)
        if _Xtream.locked_out:
            self.send_response(403)
            self.end_headers()
            return
        q = parse_qs(urlparse(self.path).query)
        ok = q.get("password", [""])[0] == GOOD_PASSWORD
        body = {"user_info": {"auth": 1 if ok else "0", "status": "Active",
                              "exp_date": "1900000000", "max_connections": "1",
                              "active_cons": "0"}, "server_info": {}}
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())


@pytest.fixture(scope="module")
def server_url():
    srv = HTTPServer(("127.0.0.1", 0), _Xtream)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://localhost:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture
def editor(qapp, db, owned_widgets):
    from streamselect.gui.provider_editor import ProviderEditorView

    ed = owned_widgets.own(ProviderEditorView(db))
    ed.start_new_source()
    return ed


def _run_test(qapp, ed) -> None:
    done = []
    ed._test_connection()
    ed._test_thread.all_done.connect(lambda r: done.append(r))
    end = time.time() + 20
    while not done and time.time() < end:
        qapp.processEvents()
        time.sleep(0.01)
    assert done, "the connection test never finished"
    qapp.processEvents()


def test_a_new_source_shows_only_what_a_new_source_has(editor):
    assert editor._save_btn.text() == "Add Source"
    assert not editor._save_btn.isEnabled(), "Add must wait for a passing test"
    assert editor._discard_btn.text() == "Cancel"
    for w in (editor._delete_btn, editor._action_refresh_btn,
              editor._action_toggle_btn):
        assert w.isHidden(), f"{w.text()!r} belongs to an existing source"


def test_wrong_then_right_credentials_can_be_added(qapp, db, editor, server_url):
    """THE regression: a failed test must not poison the next one."""
    added = []
    editor.provider_added.connect(lambda pid, epg: added.append((pid, epg)))
    editor._new_url_input.setText(server_url)          # typed, not yet added
    editor._username_input.setText("user")
    editor._password_input.setText("wrong")

    _run_test(qapp, editor)
    assert not editor._save_btn.isEnabled(), "a rejected login enabled Add"

    editor._password_input.setText(GOOD_PASSWORD)
    _run_test(qapp, editor)
    assert editor._save_btn.isEnabled(), "corrected credentials still fail the test"

    editor._name_input.setText("Fixed Source")
    editor._save_btn.click()
    assert len(added) == 1
    with db.session_scope(commit=False) as session:
        prov = session.query(ProviderDB).filter_by(id=added[0][0]).one()
        assert prov.name == "Fixed Source"
        assert prov.password == GOOD_PASSWORD
        assert prov.url == server_url
        assert prov.icon, "a new source gets an icon"


def test_editing_credentials_after_a_pass_needs_a_new_test(qapp, editor, server_url):
    editor._new_url_input.setText(server_url)
    editor._username_input.setText("user")
    editor._password_input.setText(GOOD_PASSWORD)
    _run_test(qapp, editor)
    assert editor._save_btn.isEnabled()

    editor._password_input.setText(GOOD_PASSWORD + "x")
    assert not editor._save_btn.isEnabled(), "the pass was for other credentials"

    editor._password_input.setText(GOOD_PASSWORD)
    editor._name_input.setText("Renamed")                # a name is not a credential
    assert not editor._save_btn.isEnabled()


@pytest.mark.parametrize("epg", [True, False])
def test_add_keeps_the_forms_settings(qapp, db, editor, epg):
    editor._new_url_input.setText("http://host.example:8080")
    editor._add_url()
    editor._new_url_input.setText("http://backup.example:8080")
    editor._add_url()
    editor._epg_enabled_check.setChecked(epg)
    editor._new_tested_ok = True          # the gate is covered above; this is the write
    added = []
    editor.provider_added.connect(lambda pid, e: added.append((pid, e)))
    editor._add_new_source()

    pid, emitted_epg = added[0]
    assert emitted_epg is epg
    with db.session_scope(commit=False) as session:
        prov = session.query(ProviderDB).filter_by(id=pid).one()
        assert bool(prov.epg_enabled) is epg
        assert prov.name == "host.example", "an unnamed source is named after its host"
        assert [u["url"] for u in prov.urls] == ["http://host.example:8080",
                                                 "http://backup.example:8080"]


def test_removing_an_address_from_a_new_source_just_removes_it(editor):
    for u in ("http://a.example", "http://b.example"):
        editor._new_url_input.setText(u)
        editor._add_url()
    editor._remove_url(0)
    assert [pu.url for pu in editor._provider_urls] == ["http://b.example"]
    editor._remove_url(0)       # no "at least one URL" rule before anything is saved
    assert editor._provider_urls == []


def test_every_add_source_button_opens_the_editor():
    from unittest.mock import MagicMock

    from streamselect.gui.main_window import MainWindow

    host = MagicMock()
    MainWindow.add_provider(host)
    host.switch_to_sources_manager.assert_called_once()
    host.sources_manager_view.start_new_source.assert_called_once()


@pytest.mark.parametrize("value,granted", [
    (1, True), ("1", True), (True, True), ("true", True),
    (0, False), ("0", False), ("false", False), ("", False), (None, False),
])
def test_auth_values_servers_send(value, granted):
    from streamselect.core.provider_probe import auth_granted
    assert auth_granted(value) is granted


@pytest.mark.parametrize("count,guided", [(0, True), (2, False), (None, False)])
def test_launch_with_no_source_opens_the_add_form(qapp, count, guided):
    """No source at all -> the Sources screen on a blank source; a read error is not 'none'."""
    from unittest.mock import MagicMock

    from streamselect.gui.main_window import MainWindow

    host = MagicMock()
    host.__dict__["sources_strip"] = None
    host._refresh_details_provider_map.return_value = count
    MainWindow.load_providers(host)
    qapp.processEvents()
    assert host._guide_to_first_source.called is guided


def test_the_guide_runs_once_per_session(qapp):
    """Deleting the last source later must not yank the user to the Sources screen."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from streamselect.gui.main_window import MainWindow

    host = SimpleNamespace(add_provider=MagicMock())
    MainWindow._guide_to_first_source(host)
    MainWindow._guide_to_first_source(host)
    assert host.add_provider.call_count == 1


def _wait_for(qapp, cond, what: str) -> None:
    end = time.time() + 10
    while not cond() and time.time() < end:
        qapp.processEvents()
        time.sleep(0.01)
    assert cond(), what


def test_a_pasted_m3u_link_fills_in_the_whole_account(qapp, editor, server_url):
    """User report: paste the link the provider sent and it just works."""
    editor._new_url_input.setText(
        f"{server_url}/get.php?username=user&password={quote(GOOD_PASSWORD, safe='')}"
        "&type=m3u_plus&output=ts")
    _run_test(qapp, editor)
    assert [pu.url for pu in editor._provider_urls] == [server_url]
    assert editor._username_input.text() == "user"
    assert editor._password_input.text() == GOOD_PASSWORD
    assert editor._save_btn.isEnabled(), "the link's own login did not pass"


def test_a_lockout_after_a_failed_login_is_explained_as_one(qapp, editor, server_url):
    """The stuck-test report, as the user lives it: a wrong password, then the
    right one refused (403) because the provider locked them out. The panel
    must say to wait — not blame the address, and not only the VPN."""
    editor._new_url_input.setText(server_url)
    editor._username_input.setText("user")
    editor._password_input.setText("wrong")
    _run_test(qapp, editor)
    _wait_for(qapp, lambda: "username or password" in editor._diagnosis_lbl.text(),
              "a rejected login was not explained")

    editor._password_input.setText(GOOD_PASSWORD)
    _Xtream.locked_out = True
    try:
        _run_test(qapp, editor)
        _wait_for(qapp, lambda: "answered before" in editor._diagnosis_lbl.text(),
                  "a lockout read as something else: " + editor._diagnosis_lbl.text())
    finally:
        _Xtream.locked_out = False
    assert "wait a few minutes" in editor._diagnosis_lbl.text()
    assert not editor._save_btn.isEnabled()


def test_the_intro_shows_only_while_adding(qapp, db, editor, owned_widgets):
    """It says what StreamSelect reads, never "IPTV" — and an existing source has no use for it."""
    editor.show()
    editor._tabs.setCurrentIndex(1)
    qapp.processEvents()
    intro = editor._new_source_intro
    assert intro.isVisible() and intro.height() > 0
    assert "Xtream" in intro.text() and "M3U link" in intro.text()
    assert "IPTV" not in intro.text()
    with db.session_scope() as session:
        session.add(ProviderDB(id="p1", name="Existing", type="xtream",
                               url="http://h.example", urls=[], username="u", password="p"))
    editor.load_provider("p1")
    qapp.processEvents()
    assert not intro.isVisible()
