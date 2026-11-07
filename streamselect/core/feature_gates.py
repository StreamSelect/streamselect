"""Features that are built but not yet offered to everyone.

Downloading titles and recording live channels work, but they are not finished.
Until they are, every way into them stays out of sight unless STREAMSELECT_DEV is
set. Nothing is removed: existing downloads and recordings stay in the database,
and the managers that run them still start, so anything already scheduled
finishes. Turning them on for everyone means changing :func:`capture_enabled`.
"""
from __future__ import annotations

from streamselect.core.config import dev_mode_enabled

#: Sidebar sections that belong to downloading and recording.
CAPTURE_SIDEBAR_SECTIONS = ("downloads", "recordings")
#: Settings pages that belong to downloading and recording.
CAPTURE_SETTINGS_PAGES = ("downloads", "recording")
#: Right-click menu entries that start a download or a recording.
CAPTURE_MENU_ACTIONS = ("download", "record", "record_window", "record_programme")


def capture_enabled() -> bool:
    """True when downloading and recording are offered in the interface."""
    return dev_mode_enabled()
