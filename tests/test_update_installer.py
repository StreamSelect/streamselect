"""Self-update: staging, the swap helpers, and the notice's four answers.

The macOS helper is a POSIX shell script, so it is RUN here on a real folder
tree (with ``open`` swapped for a marker command). The PowerShell helper can't
run on Linux; its tests check what it is built from, and the real proof is the
packaged Windows build.
"""

from __future__ import annotations

import os
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from streamselect.core import update_checker as uc
from streamselect.core import update_installer as ui
from streamselect.core.config import Config
from streamselect.core.notifications import NotificationManager
from streamselect.core.update_checker import UpdateInfo
from streamselect.gui import main_window_updates as mwu
from streamselect.gui.main_window_updates import _UpdatesMixin
from tests.conftest import destroy_widget


@pytest.fixture()
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _info(**kw) -> UpdateInfo:
    base = {"current": "1.0.3", "latest": "1.0.4", "is_newer": True,
            "release_url": "https://example.com/release",
            "dmg_url": "https://example.com/StreamSelect-1.0.4-arm64.dmg",
            "zip_url": "https://example.com/StreamSelect-windows-x64.zip"}
    return UpdateInfo(**{**base, **kw})


# ── Where the app lives ──────────────────────────────────────────────────────

def test_install_target_per_platform():
    mac = ui.install_target("/Applications/StreamSelect.app/Contents/MacOS/StreamSelect", "darwin")
    assert mac == Path("/Applications/StreamSelect.app")
    win = ui.install_target("C:/Apps/StreamSelect/StreamSelect.exe", "win32")
    assert win == Path("C:/Apps/StreamSelect")
    assert ui.install_target("/usr/bin/streamselect", "linux") is None
    assert ui.install_target("/somewhere/python3", "darwin") is None


def test_source_run_has_no_install_target(monkeypatch):
    monkeypatch.setattr(ui.runtime_env, "is_frozen", lambda: False)
    assert ui.install_target() is None


def test_can_self_update_needs_a_writable_parent(tmp_path):
    app = tmp_path / "StreamSelect.app"
    app.mkdir()
    assert ui.can_self_update(app)
    assert not ui.can_self_update(None)
    assert not ui.can_self_update(tmp_path / "missing.app")
    tmp_path.chmod(0o555)
    try:
        if os.access(tmp_path, os.W_OK):
            pytest.skip("running as a user that ignores permissions")
        assert not ui.can_self_update(app)
    finally:
        tmp_path.chmod(0o755)


# ── Assets ───────────────────────────────────────────────────────────────────

def test_release_assets_pick_the_windows_zip_and_platform_url():
    assets = [
        {"name": "StreamSelect-1.0.4-arm64.dmg", "browser_download_url": "https://example.com/a.dmg"},
        {"name": "StreamSelect-windows-x64.zip", "browser_download_url": "https://example.com/w.zip"},
        {"name": "StreamSelect.flatpak", "browser_download_url": "https://example.com/f.flatpak"},
    ]
    info = uc.build_update_info({"tag_name": "v1.0.4", "assets": assets}, "1.0.3")
    assert info.zip_url == "https://example.com/w.zip"
    assert uc.installer_url(info, "win32") == "https://example.com/w.zip"
    assert uc.installer_url(info, "darwin") == "https://example.com/a.dmg"
    assert uc.installer_url(info, "linux") == ""


def test_force_env_offers_a_release_that_is_not_newer(monkeypatch):
    data = {"tag_name": "v1.0.3", "assets": []}
    monkeypatch.delenv("STREAMSELECT_UPDATE_FORCE", raising=False)
    assert not uc.build_update_info(data, "1.0.3").is_newer
    monkeypatch.setenv("STREAMSELECT_UPDATE_FORCE", "1")
    assert uc.build_update_info(data, "1.0.3").is_newer


# ── Staging ──────────────────────────────────────────────────────────────────

def _windows_zip(path: Path, exe: bool = True, evil: bool = False) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        if exe:
            z.writestr("StreamSelect/StreamSelect.exe", "new")
        z.writestr("StreamSelect/mpv/mpv.exe", "mpv")
        if evil:
            z.writestr("../escaped.txt", "x")
    return path


def test_stage_windows_folder_returns_the_exe_folder(tmp_path):
    staged = ui.stage_windows_folder(_windows_zip(tmp_path / "u.zip"), tmp_path / "s")
    assert (staged / "StreamSelect.exe").read_text() == "new"
    assert (staged / "mpv" / "mpv.exe").is_file()


def test_stage_windows_folder_refuses_bad_archives(tmp_path):
    with pytest.raises(ui.UpdateInstallError):
        ui.stage_windows_folder(_windows_zip(tmp_path / "a.zip", exe=False), tmp_path / "s1")
    with pytest.raises(ui.UpdateInstallError):
        ui.stage_windows_folder(_windows_zip(tmp_path / "b.zip", evil=True), tmp_path / "s2")
    assert not (tmp_path / "escaped.txt").exists()
    bad = tmp_path / "c.zip"
    bad.write_text("not a zip")
    with pytest.raises(ui.UpdateInstallError):
        ui.stage_windows_folder(bad, tmp_path / "s3")


def test_stage_update_windows_stages_beside_the_install(tmp_path):
    target = tmp_path / "StreamSelect"
    target.mkdir()
    source = _windows_zip(tmp_path / "src.zip")
    seen = []

    def fake_download(url, dest, progress):
        progress(100)
        seen.append(dest)
        dest.write_bytes(source.read_bytes())
        return dest

    staged = ui.stage_update("https://example.com/StreamSelect-windows-x64.zip", target,
                             platform="win32", progress=lambda p: None,
                             download=fake_download)
    assert staged.parent.parent == ui.stage_dir_for(target)
    assert ui.stage_dir_for(target).parent == target.parent
    assert (staged / "StreamSelect.exe").is_file()
    assert not seen[0].exists(), "the downloaded package is deleted once unpacked"


def test_stage_update_failure_removes_the_staging_folder(tmp_path):
    target = tmp_path / "StreamSelect"
    target.mkdir()

    def broken(url, dest, progress):
        raise ui.UpdateInstallError("The download failed: offline")

    with pytest.raises(ui.UpdateInstallError):
        ui.stage_update("https://example.com/x.zip", target, platform="win32",
                        download=broken)
    assert not ui.stage_dir_for(target).exists()


def test_stage_mac_app_mounts_copies_and_detaches(tmp_path):
    calls = []

    def fake_run(argv, **kw):
        calls.append(argv[:2])
        if argv[:2] == ["hdiutil", "attach"]:
            mount = Path(argv[argv.index("-mountpoint") + 1])
            exe = mount / "StreamSelect.app" / "Contents" / "MacOS"
            exe.mkdir(parents=True)
            (exe / "StreamSelect").write_text("new")
            (mount / "Applications").mkdir()
        elif argv[0] == "ditto":
            import shutil
            shutil.copytree(argv[1], argv[2])
        elif argv[:2] == ["hdiutil", "detach"]:
            import shutil
            shutil.rmtree(argv[-1])
        return SimpleNamespace(returncode=0, stderr="")

    stage = tmp_path / "stage"
    stage.mkdir()
    app = ui.stage_mac_app(tmp_path / "u.dmg", stage, run=fake_run)
    assert app == stage / "StreamSelect.app"
    assert (app / "Contents/MacOS/StreamSelect").read_text() == "new"
    assert calls[-1] == ["hdiutil", "detach"], "the image is always unmounted"


# ── The macOS helper, run for real ───────────────────────────────────────────

def _mac_tree(tmp_path):
    parent = tmp_path / "Applications"
    target = parent / "StreamSelect.app"
    (target / "Contents").mkdir(parents=True)
    (target / "Contents" / "version").write_text("old")
    staged = ui.stage_dir_for(target) / "StreamSelect.app"
    (staged / "Contents").mkdir(parents=True)
    (staged / "Contents" / "version").write_text("new")
    return parent, target, staged


def _run_mac_helper(tmp_path, pid, target, staged):
    marker = tmp_path / "launched"
    script = tmp_path / "install.sh"
    script.write_text(ui.mac_helper_script(pid, target, staged, launch=f"touch '{marker}'"))
    subprocess.run(["/bin/sh", str(script)], check=False, timeout=30)
    return marker, script


def test_mac_helper_swaps_in_the_new_app_and_starts_it(tmp_path):
    parent, target, staged = _mac_tree(tmp_path)
    gone = subprocess.Popen(["true"])
    gone.wait()
    marker, script = _run_mac_helper(tmp_path, gone.pid, target, staged)
    assert (target / "Contents" / "version").read_text() == "new"
    assert sorted(p.name for p in parent.iterdir()) == ["StreamSelect.app"], \
        "the old app and the staging folder are removed"
    assert marker.exists(), "the new version is started"
    assert not script.exists(), "the helper deletes itself"


def test_mac_helper_waits_for_the_app_to_exit(tmp_path):
    import time
    parent, target, staged = _mac_tree(tmp_path)
    running = subprocess.Popen(["sleep", "30"])
    script = tmp_path / "install.sh"
    script.write_text(ui.mac_helper_script(running.pid, target, staged, launch="true"))
    helper = subprocess.Popen(["/bin/sh", str(script)])
    try:
        time.sleep(1.2)
        assert helper.poll() is None
        assert (target / "Contents" / "version").read_text() == "old", \
            "the swap must not start while the app runs"
    finally:
        running.kill()
        running.wait()   # reaped, as launchd reaps the real app
    helper.wait(timeout=10)
    assert (target / "Contents" / "version").read_text() == "new"


def test_mac_helper_puts_the_old_app_back_when_the_move_fails(tmp_path):
    parent, target, staged = _mac_tree(tmp_path)
    import shutil
    shutil.rmtree(staged)
    gone = subprocess.Popen(["true"])
    gone.wait()
    marker, _ = _run_mac_helper(tmp_path, gone.pid, target, staged)
    assert (target / "Contents" / "version").read_text() == "old"
    assert marker.exists(), "the old version is started again"


# ── The Windows helper (built, not run) ──────────────────────────────────────

def test_windows_helper_quotes_paths_and_restores_on_failure():
    target = Path("C:/Users/O'Neil/StreamSelect")
    staged = Path("C:/Users/O'Neil/.StreamSelect-update/unpacked/StreamSelect")
    text = ui.windows_helper_script(4242, target, staged)
    assert "'C:/Users/O''Neil/StreamSelect'" in text, "an apostrophe is doubled, not left to end the string"
    assert "Get-Process -Id 4242" in text
    wait, rename, swap = (text.index("Get-Process"), text.index("-Destination"),
                          text.index(f"Move-Item -LiteralPath '{str(staged).replace(chr(39), chr(39) * 2)}'"))
    assert wait < rename < swap, "wait for exit, move the old app aside, then move the new one in"
    assert "catch {\n  Move-Item" in text, "a failed move puts the old app back"


def test_launch_helper_starts_a_detached_script(tmp_path):
    popen = MagicMock()
    script = ui.launch_helper(tmp_path / "StreamSelect", tmp_path / "new", pid=7,
                              platform="win32", popen=popen)
    argv = popen.call_args.args[0]
    assert argv[0] == "powershell" and argv[-1] == str(script)
    assert script.read_bytes().startswith(b"\xef\xbb\xbf")
    popen.reset_mock()
    script = ui.launch_helper(tmp_path / "S.app", tmp_path / "n.app", pid=7,
                              platform="darwin", popen=popen)
    assert popen.call_args.args[0] == ["/bin/sh", str(script)]
    assert popen.call_args.kwargs["start_new_session"] is True


# ── The notice and its four answers ──────────────────────────────────────────

def _host(config=None):
    return SimpleNamespace(
        notification_manager=NotificationManager(),
        update_checker=MagicMock(),
        config=config or Config(),
        close=MagicMock(),
    )


def _bind(host):
    for name in ("_update_now", "_skip_update_version", "_never_check_for_updates",
                 "_set_update_checks_enabled", "_save_update_config",
                 "_start_update_download", "_on_update_install_failed"):
        setattr(host, name, getattr(_UpdatesMixin, name).__get__(host))
    return host


def test_notice_names_the_version_and_stays_until_answered(qapp):
    from streamselect.gui.notification_widget import NotificationCard
    host = _bind(_host())
    _UpdatesMixin._on_update_available(host, _info())
    (notice,) = host.notification_manager.get_visible_notifications()
    assert "1.0.4" in notice.title
    assert notice.dismissible is False and not notice.auto_dismiss_seconds
    assert [a[0] for a in notice.actions] == ["Now", "Later", "Skip", "Never"]

    card = NotificationCard(notice, Config())
    card.resize(360, card.sizeHint().height())
    card.show()
    qapp.processEvents()
    from PyQt6.QtWidgets import QPushButton, QToolButton
    assert not [b for b in card.findChildren((QPushButton, QToolButton))
                if b.toolTip() == "Dismiss this notification"], "no close button"
    buttons = [b for b in card.findChildren(QPushButton) if b.text() in {"Now", "Later", "Skip", "Never"}]
    assert len(buttons) == 4 and all(b.isVisible() for b in buttons)
    rects = [b.geometry() for b in buttons]
    for b in buttons:
        assert b.width() >= b.sizeHint().width(), f"{b.text()} is cut"
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            assert not a.intersects(b), "the answers overlap"
    destroy_widget(card)


def test_a_second_notice_replaces_the_first(qapp):
    host = _bind(_host())
    _UpdatesMixin._on_update_available(host, _info())
    _UpdatesMixin._on_update_available(host, _info(latest="1.0.5"))
    titles = [n.title for n in host.notification_manager.get_visible_notifications()]
    assert titles == ["StreamSelect 1.0.5 is available"]


def test_never_turns_automatic_checks_off_and_skip_records_the_version(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "save", MagicMock())
    config = Config()
    host = _bind(_host(config))
    host._never_check_for_updates()
    assert config.update_check_enabled is False
    config.save.assert_called()
    host._skip_update_version(_info())
    assert config.update_skip_version == "1.0.4"


def test_now_installs_in_place_when_the_app_can_replace_itself(tmp_path, monkeypatch, qapp):
    target = tmp_path / "StreamSelect.app"
    target.mkdir()
    monkeypatch.setattr(mwu.update_installer, "install_target", lambda: target)
    opened = MagicMock()
    monkeypatch.setattr(mwu.QDesktopServices, "openUrl", opened)
    host = _bind(_host())
    host._update_now(_info())
    host.update_checker.install_async.assert_called_once()
    assert host.update_checker.install_async.call_args.args[1] == target
    opened.assert_not_called()


def test_now_opens_the_download_page_where_it_cannot(monkeypatch, qapp):
    monkeypatch.setattr(mwu.update_installer, "install_target", lambda: None)
    monkeypatch.setattr(mwu.runtime_env, "is_macos", lambda: False)
    opened = MagicMock()
    monkeypatch.setattr(mwu.QDesktopServices, "openUrl", opened)
    host = _bind(_host())
    host._update_now(_info())
    host.update_checker.install_async.assert_not_called()
    assert opened.call_args.args[0].toString() == "https://example.com/release"


def test_staged_update_starts_the_helper_then_quits(tmp_path, monkeypatch, qapp):
    launched = MagicMock()
    monkeypatch.setattr(mwu.update_installer, "launch_helper", launched)
    shots = []
    monkeypatch.setattr(mwu.QTimer, "singleShot", lambda ms, fn: shots.append(fn))
    host = _bind(_host())
    host._update_progress_id = host.notification_manager.show_progress("Downloading", total=100)
    _UpdatesMixin._on_update_install_ready(host, (tmp_path / "a", tmp_path / "b"))
    launched.assert_called_once_with(tmp_path / "a", tmp_path / "b")
    assert shots == [host.close]


def test_helper_failure_keeps_the_app_open_and_says_why(tmp_path, monkeypatch, qapp):
    def boom(*a):
        raise ui.UpdateInstallError("Couldn't start the installer: denied")
    monkeypatch.setattr(mwu.update_installer, "launch_helper", boom)
    shots = []
    monkeypatch.setattr(mwu.QTimer, "singleShot", lambda ms, fn: shots.append(fn))
    host = _bind(_host())
    _UpdatesMixin._on_update_install_ready(host, (tmp_path / "a", tmp_path / "b"))
    assert shots == []
    (notice,) = host.notification_manager.get_visible_notifications()
    assert "denied" in notice.message


# ── Tools menu ───────────────────────────────────────────────────────────────

def test_tools_menu_toggle_follows_and_sets_the_setting(qapp, monkeypatch):
    from PyQt6.QtCore import QObject
    from PyQt6.QtWidgets import QMenu

    class Host(_UpdatesMixin, QObject):
        pass

    monkeypatch.setattr(Config, "save", MagicMock())
    host = Host()
    host.config = Config()
    host.notification_manager = NotificationManager()
    host.update_checker = MagicMock()
    menu = QMenu()
    host._add_update_menu_items(menu)
    check, auto = menu.actions()
    assert check.text() == "Software &Update…"
    assert auto.isCheckable() and auto.isChecked()

    auto.setChecked(False)
    assert host.config.update_check_enabled is False
    host.config.update_check_enabled = True   # e.g. Settings turned it back on
    menu.aboutToShow.emit()
    assert auto.isChecked()

    check.trigger()
    host.update_checker.check_async.assert_called_once_with(manual=True)
