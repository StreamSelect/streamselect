"""Migration task: store ``detected_exclusion_code`` on compound-prefix rows.

New rows get it from ``update_detected_prefixes``. Rows that already exist would
keep walking past Global Exclusions until something re-parsed them, because the
SQL predicate reads the stored code. There are only a few dozen distinct
compound prefixes, so this is one UPDATE per prefix, not a re-parse of the table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from loguru import logger

from streamselect.core.migrations.base import VersionGatedTask
from streamselect.core.region_codes import exclusion_code

if TYPE_CHECKING:
    from streamselect.core.config import Config

# Bump to re-run for every user on next launch (when exclusion_code() changes).
#   1 — initial backfill.
CURRENT_VERSION: int = 1


class ExclusionCodeBackfillTask(VersionGatedTask):
    """Fill ``detected_exclusion_code`` for each distinct compound prefix."""

    id: str = "exclusion_code_backfill"
    label: str = "Applying exclusions to compound prefixes"

    VERSION_FIELD: str = "exclusion_code_backfill_version"
    CURRENT_VERSION: int = CURRENT_VERSION

    def run(self, progress_cb: Callable[[int, int], None],
            is_cancelled: Callable[[], bool], config: "Config | None" = None) -> None:
        from streamselect.core.database import ChannelDB
        with self._db.session_scope(commit=False) as session:
            prefixes = [p for (p,) in session.query(ChannelDB.detected_prefix)
                        .filter(ChannelDB.detected_prefix.like("%-%")).distinct()]
        total = len(prefixes)
        logger.info("exclusion_code_backfill: {} distinct compound prefix(es)", total)
        progress_cb(0, total)
        for done, prefix in enumerate(prefixes, 1):
            if is_cancelled():
                return
            with self._db.session_scope() as session:
                session.query(ChannelDB).filter(ChannelDB.detected_prefix == prefix).update(
                    {ChannelDB.detected_exclusion_code: exclusion_code(prefix)},
                    synchronize_session=False)
            progress_cb(done, total)
