# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — builds a windowed, unsigned StreamSelect for macOS or Windows.

macOS produces ``dist/StreamSelect.app``; Windows produces the one-folder
``dist/StreamSelect/`` with ``StreamSelect.exe``. Everything up to ``COLLECT`` is shared;
only the icon, ``argv_emulation`` and the ``.app`` wrapper differ. Both run in
Python's UTF-8 mode (``RUNTIME_OPTIONS``).

Run from the repo root::

    pyinstaller packaging/streamselect.spec --noconfirm

Note: mpv is an EXTERNAL binary StreamSelect spawns over IPC (not libmpv), so
PyInstaller does NOT bundle it here.  CI vendors a self-contained mpv after
this build — into ``StreamSelect.app/Contents/Resources/mpv/`` (release.yml) or
``StreamSelect/mpv/`` (windows-rolling.yml); ``_resolve_mpv_binary()`` finds it there
when frozen and falls back to ``$MPV_BINARY`` / ``PATH`` otherwise.
"""

import os
import re
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ── Locate the repo root (this spec lives in <root>/packaging) ───────────────
try:
    _SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))  # noqa: F821 - PyInstaller global
except NameError:  # pragma: no cover - fallback when SPEC isn't injected
    _SPEC_DIR = os.path.abspath(os.getcwd())
REPO_ROOT = (
    os.path.dirname(_SPEC_DIR)
    if os.path.basename(_SPEC_DIR) == "packaging"
    else _SPEC_DIR
)


def _read_version() -> str:
    """Read ``__version__`` from ``streamselect/__init__.py`` (the version SSOT)."""
    init_path = os.path.join(REPO_ROOT, "streamselect", "__init__.py")
    with open(init_path, encoding="utf-8") as handle:
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', handle.read())
    return match.group(1) if match else "0.0.0"


VERSION = _read_version()

# ── Dynamically-imported plugin packages PyInstaller can't see statically ────
# providers / metadata_providers / players are loaded through factories + a
# dynamic import; whats_new entries via pkgutil.iter_modules.  Without collecting
# their submodules the frozen app would silently ship none of them.
hiddenimports: list[str] = []
for _pkg in (
    "streamselect.providers",
    "streamselect.metadata_providers",
    "streamselect.core.players",
    "streamselect.whats_new.entries",
):
    hiddenimports += collect_submodules(_pkg)
# Belt-and-suspenders: sweep the whole package so nothing dynamic is missed.
hiddenimports += collect_submodules("streamselect")

# ── Data files ───────────────────────────────────────────────────────────────
datas = []
datas += collect_data_files("qtawesome")  # bundled icon fonts / charmaps
# The window / task-switcher icon. bundle_resource_path() looks for it at
# this relative path in the frozen app, so the destination must match.
datas += [("icon/streamselect-256.png", "packaging/icon")]
# The repository's own typefaces (Inter, and the Material Symbols subset).
# streamselect/gui/fonts.py resolves them relative to the package, so they must land
# beside it in the bundle — without this the frozen app silently falls back to
# the platform default face.
datas.append(
    (
        os.path.join(REPO_ROOT, "streamselect", "assets", "fonts"),
        os.path.join("streamselect", "assets", "fonts"),
    )
)
# Also ship the What's New entry modules on disk so pkgutil.iter_modules can
# enumerate them inside the frozen app.
datas.append(
    (
        os.path.join(REPO_ROOT, "streamselect", "whats_new", "entries"),
        os.path.join("streamselect", "whats_new", "entries"),
    )
)

# ── Non-.py files the app READS AT RUNTIME ───────────────────────────────────
#
# PyInstaller follows imports, so a .py file comes along automatically and a
# data file does NOT. Every entry below is read with an open()/read_text() at
# runtime, which means omitting one is not a degraded feature — it is a
# FileNotFoundError, and if the read happens at import time it is a crash
# before any window appears.
#
# That is exactly what shipped: the DTCG palette files landed with the theme
# rewrite and were never added here, so `theme.py` -> `theme_palettes.py` ->
# `loader.build_legacy_palette()` raised FileNotFoundError on every macOS build
# from that release onward. Nothing caught it, because the suite runs from a
# source checkout where the files are simply present, and CI built the .dmg
# without ever launching it.
#
# tests/test_packaging_data_files.py asserts this list covers every non-.py
# file under streamselect/ — add a data file, and the suite tells you to add it here.
datas += [
    (os.path.join(REPO_ROOT, "streamselect", "gui", "tokens"),
     os.path.join("streamselect", "gui", "tokens")),          # *.tokens.json palettes
    (os.path.join(REPO_ROOT, "streamselect", "data"),
     os.path.join("streamselect", "data")),                   # sports_definitions.yaml
]

block_cipher = None

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"
# PyInstaller converts a PNG to .ico itself when Pillow is installed.
WINDOWS_ICON = os.path.join(REPO_ROOT, "packaging", "icon", "streamselect-256.png")

a = Analysis(
    [os.path.join(REPO_ROOT, "streamselect", "__main__.py")],
    pathex=[REPO_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Python's UTF-8 mode: every open(), pipe and log file reads and writes UTF-8
# whatever the OS locale says. Windows' locale encoding is a legacy code page
# (cp1252 in the West), so without it config.yaml, the QA notes and mpv's
# output would be read and written in a different encoding than on Linux and
# macOS, and a channel name with an emoji would fail to save. macOS is UTF-8
# already, so it gets the same behaviour it had.
RUNTIME_OPTIONS = [("X utf8_mode=1", None, "OPTION")]

exe = EXE(
    pyz,
    a.scripts,
    RUNTIME_OPTIONS,
    exclude_binaries=True,
    name="StreamSelect",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # windowed app (no attached terminal)
    disable_windowed_traceback=False,
    argv_emulation=IS_MAC,  # macOS open-document events; meaningless elsewhere
    icon=WINDOWS_ICON if IS_WINDOWS else None,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="StreamSelect",
)

if IS_MAC:
    app = BUNDLE(
        coll,
        name="StreamSelect.app",
        icon='icon/streamselect.icns' if os.path.exists('packaging/icon/streamselect.icns') else None,
        bundle_identifier="io.github.streamselect.StreamSelect",
        version=VERSION,
        info_plist={
            "CFBundleName": "StreamSelect",
            "CFBundleDisplayName": "StreamSelect",
            "CFBundleIdentifier": "io.github.streamselect.StreamSelect",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
        },
    )
