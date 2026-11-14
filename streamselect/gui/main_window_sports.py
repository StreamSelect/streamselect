"""``_SportsViewMixin`` — the Sports view's place in the window: build, switch, toggle.

Mixed into :class:`~streamselect.gui.main_window.MainWindow` like every other
``main_window_*`` mixin. The view is built on first use (most sessions never
open it) into the same content layout as the other views, and listed in
``main_window_nav.CONTENT_VIEW_ATTRS`` so every view switch hides and
deactivates it through the one seam.
"""

from __future__ import annotations

from streamselect.gui.sports_view import SportsView


class _SportsViewMixin:
    """Mixin: the Sports view (games on now and coming up)."""

    def _ensure_sports_view(self) -> SportsView:
        view = self.__dict__.get("sports_view")
        if view is None:
            view = self.sports_view = SportsView(self.db, self.config, self._run_query, self,
                                                 image_cache=self.image_cache)
            view.playRequested.connect(self.play_channel_by_id)
            view.channelSelected.connect(self.show_channel_details_by_id)
            # The card's "Hide this channel everywhere…" is the app's own Hide.
            view.hideEverywhereRequested.connect(lambda cid: self._bulk_hide_channels([cid]))
            view.alertsChanged.connect(self._refresh_sports_alerts)
            view.setVisible(False)
            self._list_layout.addWidget(view)
            # A run starting says "finding" instead of a premature 0; new games stored
            # re-read on screen (an unseen view re-reads on its next activate).
            tracker = self.game_tracker
            tracker.finding_started.connect(lambda: view.set_finding(True))
            tracker.games_updated.connect(lambda _counts: view.finished_finding())
        return view

    def _refresh_sports_alerts(self) -> None:
        """Re-read the Watch Alerts Sports group (a bell changed, or games were re-found)."""
        section = self.sidebar_sections.get("alerts")
        if section is not None:
            section.refresh_sports()

    def switch_to_sports_view(self) -> None:
        """Switch the content area to the Sports view."""
        # A user-picked view cancels the first-run hand-off (see switch_to_list_view).
        self.__dict__.pop("_first_source_pending", None)
        self.view_mode = "sports"
        self._hide_all_content_views()
        view = self._ensure_sports_view()
        tracker = self.game_tracker
        if not tracker.has_run and not tracker.busy:
            tracker.request()          # opened before the first run after launch: run it now
        view.set_finding(tracker.busy)
        view.setVisible(True)
        self.stats_label.setText("Sports")
        view.on_activate()
        self._offer_view_tip("sports")

    def on_sports_view_toggle(self) -> None:
        if self.sports_chip.is_enabled():
            self._deactivate_view_chips(self.sports_chip)
            self.switch_to_sports_view()
        else:
            self.switch_to_list_view()
