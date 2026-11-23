"""Where a play starts: the one reading of Settings ▸ Playback's resume choice.

Movies (``main_window_streaming``) and episodes (``play_episode_by_id``, which the
History, Watch Queue and Favorites rows use) both start here, so a double-click
resumes or starts over the same way on every surface. Episodes opened from those
rows always started at 0 until 2026-11-23, whatever the setting said.
"""

from __future__ import annotations


def default_start_seconds(watch_progress: int | None, resume_mode: str) -> int:
    """The position a plain play starts from: the saved one when the user resumes
    (``playback_resume_mode == "resume"``, the default), else the beginning."""
    return max(0, int(watch_progress or 0)) if resume_mode == "resume" else 0
