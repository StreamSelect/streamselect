"""Watch Alerts remembers which groups and EPG show rows the user collapsed.

The group headings (EPG, Sports, Series, Watching for, Stream Monitoring) and each
EPG show row's open/closed choice used to live only in memory, so every launch
re-opened them, and the automatic room-fitting re-opened shows the user had shut
(owner report, 2026-11-18). One entry in ``Config.sidebar_section_states`` holds
both, beside the section's own collapsed state and height.
"""

from __future__ import annotations

from streamselect.gui import deferred_config_save as _cfgsave

#: The key in ``sidebar_section_states``; the section's own entry is "alerts".
FOLDS_KEY = "alerts_groups"
#: group name -> the section attribute holding "collapsed".
GROUP_FLAGS = {
    "epg": "_epg_collapsed",
    "sports": "_sports_collapsed",
    "series": "_series_collapsed",
    "movies": "_keyword_collapsed",
    "monitoring": "_retry_collapsed",
}
#: Show rows remembered, most recently chosen kept: shows come and go.
MAX_ROWS = 200


class AlertFoldsMixin:
    """Restore after ``create_content``; save on every user toggle."""

    def _restore_folds(self) -> None:
        state = (getattr(self.config, "sidebar_section_states", None) or {}).get(FOLDS_KEY) or {}
        groups = state.get("groups") or {}
        for name, attr in GROUP_FLAGS.items():
            if name in groups:
                setattr(self, attr, bool(groups[name]))
        self._user_expansion.update({str(k): bool(v) for k, v in (state.get("rows") or {}).items()})
        retry = self.__dict__.get("_retry_list")
        if retry is not None and self._retry_collapsed:
            retry.hide()

    def _save_folds(self) -> None:
        rows = list(self._user_expansion.items())[-MAX_ROWS:]
        self.config.sidebar_section_states[FOLDS_KEY] = {
            "groups": {name: bool(self.__dict__.get(attr, False)) for name, attr in GROUP_FLAGS.items()},
            "rows": dict(rows),
        }
        _cfgsave.save_soon(self)
