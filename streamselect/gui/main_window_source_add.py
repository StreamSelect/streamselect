"""Adding sources: the one Add path, the first-run guide, the no-usable-source
notice, and re-adding after a fresh start.

Mixed into :class:`~streamselect.gui.main_window.MainWindow`. Split out of
``main_window_providers`` (which edits, refreshes and deletes sources) because
adding is its own job: every Add Source button, the launch with no sources and
the Fresh-start-keep-sources restore all end in ``_on_provider_added``. The
notice is the same job's other half: when there is nothing to read from, say so
and point at Add Source (or Sources) until there is.
"""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QTimer
from loguru import logger

from streamselect.core.repositories import RepositoryFactory
from streamselect.gui.empty_state import no_source_notice_text

#: Longest single wait before the expiry re-check looks again. A machine that
#: sleeps past a source's end date wakes into a timer that was counting
#: wall-clock-blind, so the check never sleeps longer than this.
_EXPIRY_RECHECK_CAP_MS = 6 * 60 * 60 * 1000


class _SourceAddMixin:
    """Add Source, the first-run guide, and the fresh-start restore."""

    def add_provider(self):
        """Open the Sources screen on a new, blank source — the ONE Add path.

        Every Add Source button lands here (sidebar, menu, Sources header,
        empty states), so a source is added on the same form it is edited on
        and the user sees where sources live (the design notes, "One
        process, never a parallel flow").
        """
        self.switch_to_sources_manager()
        self.sources_manager_view.start_new_source()

    def _on_provider_added(self, provider_id: str, epg_enabled: bool) -> None:
        """A new source was added in the editor: show it, then load it."""
        with self.db.session_scope(commit=False) as session:
            row = RepositoryFactory(session).providers.get_by_id(provider_id)
            name = row.name if row else "your source"
        # Until its first load finishes, the empty state says it is loading.
        self.__dict__.setdefault("_first_loading", {})[provider_id] = name
        if epg_enabled:
            # Fetch the guide once its first channel load finishes
            # (consumed by on_provider_refresh_finished).
            self._epg_fetch_after_add.add(provider_id)
        self._refresh_provider_dependent_views()
        self.sources_manager_view.refresh()
        self.sources_manager_view.select_provider(provider_id)
        self.refresh_provider(provider_id)
        self.status("Source added — loading its channels.", ms=5000)

    def restore_sources(self, sources: list[dict]) -> None:
        """After a fresh start that kept sources: add each one back, as if just added.

        Same path as Add Source (``_on_provider_added``): the row is written,
        the views refresh, the channels load and the guide is fetched. URL
        statistics start empty, like a new source.
        """
        from streamselect.core.database import ProviderDB
        from streamselect.core.models import ProviderURL
        from streamselect.core.repositories.provider import provider_url_to_raw

        self._guided_to_first_source = True     # sources are on their way
        with self.db.session_scope() as session:
            for src in sources:
                fields = dict(src)
                urls = [u.get("url") if isinstance(u, dict) else u
                        for u in (fields.pop("urls", None) or [])] or [fields["url"]]
                fields["urls"] = [provider_url_to_raw(ProviderURL(url=u), priority=i)
                                  for i, u in enumerate(urls)]
                session.add(ProviderDB(**fields))
        for src in sources:
            self._on_provider_added(src["id"], bool(src.get("epg_enabled", True)))

    def _guide_to_first_source(self) -> None:
        """At launch with no sources: open the Sources screen on a blank source.

        Once per session, so deleting the last source later does not yank the
        user away from wherever they are.
        """
        if self.__dict__.get("_guided_to_first_source"):
            return
        self._guided_to_first_source = True
        self.add_provider()

    # ── the no-usable-source notice ─────────────────────────────────────────

    def _sync_no_source_notice(self) -> None:
        """Show, re-word or close the persistent no-source notice.

        Called from ``load_providers`` — the step every source mutation reaches
        through ``_refresh_provider_dependent_views`` — so launch, delete,
        turn off and expiry all land here. It never re-shows a notice the user
        closed while the cause is unchanged; a NEW cause (the last source was
        removed, or expired) shows it again.
        """
        try:
            with self.db.session_scope(commit=False) as session:
                avail = RepositoryFactory(session).providers.get_availability()
        except Exception:
            logger.opt(exception=True).warning("no-source notice: could not count sources")
            return
        self._known_expired = avail.expired
        self._source_availability = avail
        self._sync_empty_state()
        self._schedule_expiry_recheck(avail.next_expiry_at)
        text = no_source_notice_text(avail)
        shown = self.__dict__.get("_no_source_notice")      # (title, notification id)
        if shown and (text is None or text[0] != shown[0]):
            self.notification_manager.dismiss(shown[1])
            self._no_source_notice = None
        if text is None or (shown and text[0] == shown[0]):
            return
        title, message, action = text
        button = (("Add Source", self.add_provider) if action == "add"
                  else ("Open Sources", self.switch_to_sources_manager))
        nid = self.notification_manager.show(
            title=title, message=message, type="warning",
            actions=[button], dismissible=True)
        self._no_source_notice = (title, nid)

    def _schedule_expiry_recheck(self, when: datetime | None) -> None:
        """Re-run the source refresh the moment the next subscription ends."""
        timer = self.__dict__.get("_expiry_recheck_timer")
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._on_expiry_recheck)
            self._expiry_recheck_timer = timer
        timer.stop()
        if when is None:
            return
        ms = int((when - datetime.now()).total_seconds() * 1000) + 1000
        timer.start(max(1000, min(ms, _EXPIRY_RECHECK_CAP_MS)))

    def _on_expiry_recheck(self) -> None:
        """A subscription may have just ended: refresh everything only if one did.

        An expired source is hidden everywhere (``get_hidden_provider_ids``), so
        an expiry is a source mutation and takes the canonical refresh — which
        ends back in ``_sync_no_source_notice``. The capped wake-ups that find
        nothing new only re-arm the timer.
        """
        try:
            with self.db.session_scope(commit=False) as session:
                avail = RepositoryFactory(session).providers.get_availability()
        except Exception:
            logger.opt(exception=True).warning("expiry re-check: could not count sources")
            return
        if avail.expired != self.__dict__.get("_known_expired"):
            self._refresh_provider_dependent_views()
        else:
            self._schedule_expiry_recheck(avail.next_expiry_at)

    # ── after a new source's first scan: point at Exclusions ────────────────

    def _announce_first_scan(self, provider_id: str) -> None:
        """Say what a new source brought in, and where to hide what isn't wanted.

        A user (Q9/R7): after a new source's first scan, tell the
        user that the Exclusions chip in the top bar is where regions and
        languages are hidden everywhere, and pulse the chip. The counts are
        this source's alone — every other source is excluded from the query.
        """
        def count(repos):
            others = [p.id for p in repos.providers.get_all() if p.id != provider_id]
            return tuple(len(repos.tags.get_tag_counts_for_facet(facet, excluded_provider_ids=others))
                         for facet in ("region", "language"))

        # A failed count still deserves the pointer — just without the numbers.
        self._run_query(count, lambda counts: self._show_first_scan_notice(*counts),
                        on_error=lambda exc: (
                            logger.warning("first-scan counts failed: {}", exc),
                            self._show_first_scan_notice(0, 0)))

    def _show_first_scan_notice(self, regions: int, languages: int) -> None:
        found = " and ".join(
            f"{n:,} {word}{'' if n == 1 else 's'}"
            for n, word in ((regions, "region"), (languages, "language")) if n)
        lead = f"Found {found}. " if found else ""
        chip = self.__dict__.get("_filter_chip")
        actions = [("Open Exclusions", self._open_global_filter_dialog)]
        tour = ""
        # The tour is offered here, once: now the views have something in
        # them to point at (user report). Never again once taken.
        from streamselect.gui.guided_tour import TOUR_MENU_PATH
        from streamselect.gui.just_in_time_tips import TOUR_KEY, seen
        if not seen(self, TOUR_KEY):
            actions.append(("Take the tour", self.start_tour))
            tour = f" New here? A one-minute tour is always in {TOUR_MENU_PATH}."
        self.notification_manager.show(
            title="Your source is ready",
            message=(f"{lead}To hide any you don't want, everywhere, use "
                     f"Exclusions in the top bar.{tour}"),
            type="info", auto_dismiss_seconds=None if tour else 30,
            actions=actions)
        if chip is not None:
            from streamselect.gui.attention_pulse import pulse
            pulse(chip)
