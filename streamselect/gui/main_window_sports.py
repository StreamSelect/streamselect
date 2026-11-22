"""``_SportsViewMixin`` — the Sports view's place in the window: build, switch, toggle.

Mixed into :class:`~streamselect.gui.main_window.MainWindow` like every other
``main_window_*`` mixin. The view is built on first use (most sessions never
open it) into the same content layout as the other views, and listed in
``main_window_nav.CONTENT_VIEW_ATTRS`` so every view switch hides and
deactivates it through the one seam.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog

from streamselect.core.games import tuning
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
            # First-time help: the Sports tour, then one-off tips (sports_tips).
            view.rendered.connect(self._offer_sports_tips)
            view.leagueHidden.connect(self._offer_league_hidden_tip)
            view.setVisible(False)
            self._list_layout.addWidget(view)
            # A run starting says "finding" instead of a premature 0; new games stored
            # re-read on screen (an unseen view re-reads on its next activate).
            tracker = self.game_tracker
            tracker.finding_started.connect(lambda: view.set_finding(True))
            tracker.games_updated.connect(lambda _counts: view.finished_finding())
        return view

    def _offer_sports_tips(self) -> None:
        from streamselect.gui.sports_tips import on_rendered
        on_rendered(self, self.sports_view)

    def _offer_league_hidden_tip(self, sport: str, league: str) -> None:
        from streamselect.gui.sports_tips import on_league_hidden
        on_league_hidden(self, self.sports_view, sport, league)

    def maybe_offer_improved_defaults(self) -> None:
        """After an update: if a default moved for a Sports setting the user had set,
        ask keep-mine or take-new, once (SS-Q8/Q9). Values the user never set have
        already moved with the default; "don't ask again" keeps theirs for good."""
        config = self.config
        items = tuning.improved(config.sport_settings_overrides)
        if not items:
            return
        overrides = dict(config.sport_settings_overrides)
        if not config.ask_about_improved_defaults:
            for item in items:
                tuning.keep_mine(overrides, item)     # noted, so nothing piles up to ask later
        else:
            from streamselect.gui.improved_defaults_dialog import ImprovedDefaultsDialog
            dlg = ImprovedDefaultsDialog(items, self)
            accepted = dlg.exec() == QDialog.DialogCode.Accepted
            dlg.apply_to(overrides, accepted)
            if dlg.never.isChecked():
                config.ask_about_improved_defaults = False
        config.sport_settings_overrides = overrides
        config.save()
        self._apply_sports_settings()

    def _apply_sports_settings(self) -> None:
        """Settings ▸ Sports was saved: every Sports surface takes the new numbers."""
        view = self.__dict__.get("sports_view")
        if view is not None:
            view.settings_changed()
        self._refresh_sports_alerts()
        tracker = self.__dict__.get("game_tracker")
        if tracker is not None:
            tracker.request()          # listing windows and finder numbers may have changed

    def _refresh_sports_alerts(self) -> None:
        """A bell, a game's state or the stored games changed: every alert surface re-reads
        now — the Watch Alerts Sports group, and the event-alert check the tray's live
        icon follows (else up to its 30 s poll late)."""
        section = self.sidebar_sections.get("alerts")
        if section is not None:
            section.refresh_sports()
        notifier = self.__dict__.get("event_alert_notifier")
        if notifier is not None:
            notifier.check()

    def switch_to_sports_view(self) -> None:
        """Switch the content area to the Sports view."""
        # A user-picked view cancels the first-run hand-off (see switch_to_list_view).
        self.__dict__.pop("_first_source_pending", None)
        self.view_mode = "sports"
        self._hide_all_content_views()
        view = self._ensure_sports_view()
        tracker = self.game_tracker
        tracker.request_first()        # opened before the first run after launch: run it now
        view.set_finding(tracker.busy)
        view.setVisible(True)
        self.stats_label.setText("Sports")
        view.on_activate()

    def on_sports_view_toggle(self) -> None:
        if self.sports_chip.is_enabled():
            self._deactivate_view_chips(self.sports_chip)
            self.switch_to_sports_view()
        else:
            self.switch_to_list_view()
