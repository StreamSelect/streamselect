"""Install a downloaded update in place: macOS ``.app`` and the Windows folder.

The running app cannot replace its own files, so installing has three parts:

1. **Stage** (in the app, on a worker thread): download the release asset and
   unpack the new app into a hidden folder BESIDE the installed one. Same
   folder means same volume, so the swap below is a rename, never a copy.
2. **Hand off**: write a small helper script and start it detached, then the
   app quits normally (``closeEvent`` runs its cleanup).
3. **Swap** (the helper): wait for the app's process to exit, rename the old
   app aside, move the new one into its place, start it, and delete the old
   one. If moving the new one in fails, the old one is put back and started.

Nothing here touches user data: it lives outside the install on every platform
(``core/app_paths.py``). Linux is not handled here; it gets the notification
only, and its "Now" opens the download page.

No Qt in this module, so every step is testable without an event loop. The
helper scripts are built from literal, quoted paths, never shell variables
holding a path that a failure could leave empty.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from loguru import logger

from streamselect.core import runtime_env

_DOWNLOAD_TIMEOUT = 120
_CHUNK = 256 * 1024
STAGE_PREFIX = ".StreamSelect-update"
_MAC_EXE = "Contents/MacOS/StreamSelect"
_WIN_EXE = "StreamSelect.exe"
# Seconds the helper waits for the app to exit before giving up untouched.
_WAIT_SECONDS = 60

ProgressFn = Callable[[int], None]


class UpdateInstallError(Exception):
    """A step of the install failed; the message is shown to the user."""


# ── Where the app is installed ───────────────────────────────────────────────

def install_target(executable: Optional[str] = None,
                   platform: Optional[str] = None) -> Optional[Path]:
    """The folder the update replaces, or ``None`` when this build can't self-update.

    macOS: the ``StreamSelect.app`` bundle holding the executable.
    Windows: the one-folder build holding ``StreamSelect.exe``.
    Source runs and Linux return ``None``.
    """
    platform = platform or sys.platform
    if executable is None:
        if not runtime_env.is_frozen():
            return None
        executable = sys.executable
    exe = Path(executable)
    if platform == "darwin":
        for parent in exe.parents:
            if parent.suffix == ".app":
                return parent
        return None
    if platform == "win32":
        return exe.parent
    return None


def can_self_update(target: Optional[Path]) -> bool:
    """True when *target* exists and its parent folder is writable.

    A read-only parent is the common reason to fall back: a Windows build in
    Program Files, a Mac app still on the disk image, or one macOS runs from a
    read-only copy because it was never moved out of Downloads.
    """
    if target is None or not target.is_dir():
        return False
    return os.access(target.parent, os.W_OK)


def stage_dir_for(target: Path) -> Path:
    """The hidden staging folder beside *target*."""
    return target.parent / STAGE_PREFIX


# ── Download ────────────────────────────────────────────────────────────────

def download_file(url: str, dest: Path, progress: Optional[ProgressFn] = None,
                  timeout: int = _DOWNLOAD_TIMEOUT) -> Path:
    """Download *url* to *dest*, reporting whole percents to *progress*.

    Raises:
        UpdateInstallError: on any network or disk failure.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "StreamSelect-Updater"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, \
                open(dest, "wb") as handle:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            last = -1
            while True:
                chunk = response.read(_CHUNK)
                if not chunk:
                    break
                handle.write(chunk)
                done += len(chunk)
                if progress and total:
                    pct = min(100, done * 100 // total)
                    if pct != last:
                        last = pct
                        progress(pct)
    except (urllib.error.URLError, OSError) as exc:
        raise UpdateInstallError(f"The download failed: {exc}") from exc
    return dest


# ── Unpack into the staging folder ───────────────────────────────────────────

def stage_mac_app(dmg: Path, stage: Path,
                  run: Callable = subprocess.run) -> Path:
    """Mount *dmg*, copy its ``.app`` into *stage*, unmount. Returns the new ``.app``."""
    mount = Path(tempfile.mkdtemp(prefix="streamselect-dmg-"))
    try:
        result = run(["hdiutil", "attach", "-nobrowse", "-readonly", "-noautoopen",
                      "-mountpoint", str(mount), str(dmg)],
                     capture_output=True, text=True)
        if result.returncode != 0:
            raise UpdateInstallError(f"Couldn't open the disk image: {result.stderr.strip()}")
        try:
            apps = sorted(p for p in mount.iterdir() if p.suffix == ".app")
            if not apps:
                raise UpdateInstallError("The disk image has no app in it.")
            new_app = stage / apps[0].name
            # ditto keeps the bundle's signature, symlinks and permissions.
            copied = run(["ditto", str(apps[0]), str(new_app)],
                         capture_output=True, text=True)
            if copied.returncode != 0:
                raise UpdateInstallError(f"Couldn't copy the new app: {copied.stderr.strip()}")
        finally:
            run(["hdiutil", "detach", "-quiet", str(mount)], capture_output=True, text=True)
    finally:
        try:
            mount.rmdir()
        except OSError:
            pass
    if not (new_app / _MAC_EXE).is_file():
        raise UpdateInstallError("The new app is incomplete.")
    return new_app


def stage_windows_folder(zip_path: Path, stage: Path) -> Path:
    """Unzip *zip_path* into *stage*. Returns the folder holding ``StreamSelect.exe``."""
    try:
        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.namelist():
                # Refuse anything that would land outside the staging folder.
                resolved = (stage / member).resolve()
                if not resolved.is_relative_to(stage.resolve()):
                    raise UpdateInstallError("The update archive is malformed.")
            archive.extractall(stage)
    except zipfile.BadZipFile as exc:
        raise UpdateInstallError("The update archive is damaged.") from exc
    for candidate in (stage / "StreamSelect", stage):
        if (candidate / _WIN_EXE).is_file():
            return candidate
    raise UpdateInstallError("The update archive has no StreamSelect.exe in it.")


def stage_update(url: str, target: Path, platform: Optional[str] = None,
                 progress: Optional[ProgressFn] = None,
                 run: Callable = subprocess.run,
                 download: Callable = download_file) -> Path:
    """Download the asset at *url* and unpack the new app next to *target*.

    Returns the staged app (``.app`` bundle or Windows folder). A staging
    folder left by an earlier, interrupted attempt is cleared first.

    Raises:
        UpdateInstallError: on any failure; the staging folder is removed.
    """
    platform = platform or sys.platform
    stage = stage_dir_for(target)
    if stage.exists():
        shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    try:
        name = url.rsplit("/", 1)[-1] or "update"
        package = download(url, stage / name, progress)
        if platform == "darwin":
            staged = stage_mac_app(package, stage, run=run)
        elif platform == "win32":
            staged = stage_windows_folder(package, stage / "unpacked")
        else:
            raise UpdateInstallError("This system updates from the download page.")
        package.unlink(missing_ok=True)
        return staged
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


# ── The helper that swaps after the app exits ────────────────────────────────

def _ps(value: str) -> str:
    """A PowerShell single-quoted literal."""
    return "'" + value.replace("'", "''") + "'"


def mac_helper_script(pid: int, target: Path, staged: Path,
                      launch: Optional[str] = None) -> str:
    """POSIX shell script that swaps *staged* in for *target* once *pid* exits.

    *launch* is the command that starts the app afterwards; it defaults to
    ``open <target>`` and is replaceable so tests can run the script on Linux.
    """
    t, s = shlex.quote(str(target)), shlex.quote(str(staged))
    old = shlex.quote(str(target.parent / f"{STAGE_PREFIX}-old.app"))
    stage = shlex.quote(str(stage_dir_for(target)))
    launch = launch or f"open {t}"
    tries = _WAIT_SECONDS * 2
    return f"""#!/bin/sh
# StreamSelect update: replace the app once it has quit, then start it.
n=0
while kill -0 {pid} 2>/dev/null; do
  n=$((n+1)); [ "$n" -gt {tries} ] && exit 1
  sleep 0.5
done
rm -rf {old}
mv {t} {old} || exit 1
if mv {s} {t}; then
  rm -rf {old}
  xattr -dr com.apple.quarantine {t} 2>/dev/null
else
  mv {old} {t}
fi
rm -rf {stage}
{launch}
rm -f "$0"
"""


def windows_helper_script(pid: int, target: Path, staged: Path) -> str:
    """PowerShell script that swaps *staged* in for *target* once *pid* exits.

    Renaming the old folder is retried: a file in it can stay locked for a
    moment after exit (a player child process, an antivirus scan).
    """
    old = target.parent / f"{STAGE_PREFIX}-old"
    exe = target / _WIN_EXE
    return f"""$ErrorActionPreference = 'Stop'
# StreamSelect update: replace the app once it has quit, then start it.
$deadline = (Get-Date).AddSeconds({_WAIT_SECONDS})
while (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{
  if ((Get-Date) -gt $deadline) {{ exit 1 }}
  Start-Sleep -Milliseconds 500
}}
if (Test-Path -LiteralPath {_ps(str(old))}) {{
  Remove-Item -LiteralPath {_ps(str(old))} -Recurse -Force
}}
$moved = $false
for ($i = 0; $i -lt 40 -and -not $moved; $i++) {{
  try {{ Move-Item -LiteralPath {_ps(str(target))} -Destination {_ps(str(old))}; $moved = $true }}
  catch {{ Start-Sleep -Milliseconds 500 }}
}}
if (-not $moved) {{ Start-Process -FilePath {_ps(str(exe))}; exit 1 }}
try {{
  Move-Item -LiteralPath {_ps(str(staged))} -Destination {_ps(str(target))}
}} catch {{
  Move-Item -LiteralPath {_ps(str(old))} -Destination {_ps(str(target))}
}}
Start-Process -FilePath {_ps(str(exe))}
Remove-Item -LiteralPath {_ps(str(old))} -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath {_ps(str(stage_dir_for(target)))} -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
"""


def launch_helper(target: Path, staged: Path, pid: Optional[int] = None,
                  platform: Optional[str] = None,
                  popen: Callable = subprocess.Popen) -> Path:
    """Write the helper script for this platform and start it detached.

    The app must quit right after this returns; the helper waits for it.

    Raises:
        UpdateInstallError: if the script can't be written or started.
    """
    platform = platform or sys.platform
    pid = pid if pid is not None else os.getpid()
    scripts = Path(tempfile.mkdtemp(prefix="streamselect-update-"))
    try:
        if platform == "darwin":
            script = scripts / "install.sh"
            script.write_text(mac_helper_script(pid, target, staged), encoding="utf-8")
            script.chmod(0o755)
            popen(["/bin/sh", str(script)], start_new_session=True, close_fds=True,
                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                  stderr=subprocess.DEVNULL)
        elif platform == "win32":
            script = scripts / "install.ps1"
            # BOM: Windows PowerShell 5.1 reads a BOM-less file as the ANSI
            # code page, which would mangle a non-ASCII install path.
            script.write_text(windows_helper_script(pid, target, staged),
                              encoding="utf-8-sig")
            flags = (getattr(subprocess, "DETACHED_PROCESS", 0)
                     | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
            popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                   "-WindowStyle", "Hidden", "-File", str(script)],
                  creationflags=flags, close_fds=True,
                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                  stderr=subprocess.DEVNULL)
        else:
            raise UpdateInstallError("This system updates from the download page.")
    except OSError as exc:
        raise UpdateInstallError(f"Couldn't start the installer: {exc}") from exc
    logger.info(f"Update helper started: {script}")
    return script
