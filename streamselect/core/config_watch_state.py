"""Monitored series and VOD watch-alert state, as methods on ``Config``.

Split out of ``config.py`` (ledger F68): these are DATA operations on two stored
lists (``monitored_series`` and ``vod_watch_alerts``), not settings. ``Config``
inherits this mixin, so every ``config.add_vod_watch_alert(...)`` call site is
unchanged; the fields themselves stay declared in ``config.py`` with the rest
of the settings register.
"""

from __future__ import annotations


class _WatchStateMixin:
    """Methods over ``Config.monitored_series`` and ``Config.vod_watch_alerts``."""

    def add_monitored_series(self, entry: dict) -> None:
        """Add a series to the monitor list (no-op if already present)."""
        cid = entry.get("series_channel_id")
        if not cid:
            return
        if not self.is_series_monitored(cid):
            self.monitored_series = list(self.monitored_series) + [entry]
            self.save()

    def remove_monitored_series(self, series_channel_id: str) -> None:
        """Remove a series from the monitor list."""
        self.monitored_series = [
            e for e in self.monitored_series
            if e.get("series_channel_id") != series_channel_id
        ]
        self.save()

    def is_series_monitored(self, series_channel_id: str) -> bool:
        """Return True if the given series_channel_id is in the monitor list."""
        return any(
            e.get("series_channel_id") == series_channel_id
            for e in self.monitored_series
        )

    def get_monitored_series(self) -> list:
        """Return a copy of the monitored series list.

        Migrates any legacy entry (scalar ``baseline_episode_count``, from
        before the per-provider baselines upgrade) to the per-provider
        ``baselines`` shape, AND resets any ``unseen_new`` left inflated by
        the an earlier change baseline-accounting bug (a flaky provider fetch recorded a
        baseline of 0, so the next successful check counted the whole
        catalogue as "new" every pass) to 0 — a count found exceeding its
        summed baselines is PROVEN corrupt (no way to tell which, if any, of
        the recorded episodes were genuine new ones), so 0 is the honest
        value, not a clamped guess; genuinely new episodes are detected fresh
        on the very next check regardless.  Both steps run on first read,
        writing the migrated list back, and are one-time, idempotent upgrades
        (see ``series_monitor.normalize_monitored_entry`` and
        ``series_monitor.zero_out_inflated_unseen_new`` — NOT the different,
        ongoing ``clamp_unseen_new_to_baseline_total`` guard applied to fresh
        writes in ``SeriesMonitorManager._on_new_episodes``).  Entries
        already sane pass through unchanged.  This never touches favorites,
        ratings, history, or watch progress, and never removes an entry — it
        only ever corrects the derived ``unseen_new``/``baselines`` fields on
        this list.
        """
        from streamselect.core.series_monitor import (
            normalize_monitored_entry,
            zero_out_inflated_unseen_new,
        )

        changed = False
        migrated = []
        for e in self.monitored_series:
            m = normalize_monitored_entry(e)
            c = zero_out_inflated_unseen_new(m)
            if c is not e:
                changed = True
            migrated.append(c)
        if changed:
            self.monitored_series = migrated
            self.save()
        return list(self.monitored_series)

    def get_monitored_for_provider(self, provider_id: str) -> list:
        """Return monitored series entries that involve the given provider.

        Matches the entry's PRIMARY provider (the source the user clicked
        "Alert me" from) OR any provider already recorded in its per-provider
        ``baselines`` dict — so a call after THAT mirror's refresh also finds
        entries discovered as siblings by a prior full ``check_all()`` pass.
        """
        from streamselect.core.series_monitor import provider_of

        # provider_of, not a bare `in`: baseline keys are "provider|source"
        # (one slot per mirror), so a plain membership test never matches.
        return [
            e for e in self.get_monitored_series()
            if e.get("provider_id") == provider_id
            or any(
                provider_of(k) == provider_id
                for k in (e.get("baselines") or {})
            )
        ]

    def update_monitored_series(
        self, series_channel_id: str, *, save: bool = True, **fields
    ) -> None:
        """Update fields on an existing monitored series entry, in place.

        Args:
            series_channel_id: Entry to update.
            save: Write the file now. Pass ``False`` when several updates are
                coming in a row and the caller will call :meth:`save` once
                itself. The entry is updated IN MEMORY either way, immediately —
                only the file write is deferred. That distinction matters: the
                Watch Alerts badges read ``unseen_new`` straight back, so
                deferring the in-memory update would make new-episode counts lag
                a whole pass, while deferring the SAVE costs nothing visible.
            **fields: Fields to merge onto the entry.
        """
        updated = []
        for e in self.monitored_series:
            if e.get("series_channel_id") == series_channel_id:
                merged = dict(e)
                merged.update(fields)
                updated.append(merged)
            else:
                updated.append(e)
        self.monitored_series = updated
        if save:
            self.save()

    def update_monitored_series_many(self, updates: dict) -> None:
        """Apply field updates to many entries and save **once**.

        :meth:`update_monitored_series` saves on every call, which is right for
        a single user action and ruinous in a loop. Each save copies the config
        to ``.bak``, runs a full Pydantic ``model_dump()`` and re-serialises the
        whole file — and this config is not small (a user's: many
        lines / 132 KB, three quarters of it QA results, derived filter caches
        and an ever-growing collapsed-shelf list).

        Two paths were paying that per iteration, BOTH on the main thread:

        * ``SeriesMonitorManager._on_new_episodes`` — a queued-signal slot fired
          once per checked series. Not a loop, so a time-based debounce cannot
          coalesce it: the signals arrive seconds apart across a pass. It writes
          in memory immediately and lets the pass boundary do the one save.
        * ``MainWindow._apply`` (the ``_run_query`` callback that backfills
          region/language) — once per row, where the cost
          is not merely contention but a direct freeze.

        Args:
            updates: ``{series_channel_id: {field: value, ...}}``. Ids not
                present in ``monitored_series`` are ignored, matching
                :meth:`update_monitored_series`'s behaviour for an unknown id.
        """
        if not updates:
            return
        changed = False
        merged_list = []
        for e in self.monitored_series:
            fields = updates.get(e.get("series_channel_id"))
            if fields:
                merged = dict(e)
                merged.update(fields)
                merged_list.append(merged)
                changed = True
            else:
                merged_list.append(e)
        if not changed:
            return
        self.monitored_series = merged_list
        self.save()

    def clear_unseen(self, series_channel_id: str) -> None:
        """Reset unseen_new (+ its per-mirror breakdown and provider attribution)
        to 0 for the given series.

        Called both by the explicit "Mark seen" action and by drilling into the
        series' season/episode tree (opening it is itself an acknowledgment).
        """
        self.update_monitored_series(
            series_channel_id, unseen_new=0, unseen_by_mirror={}, growth_providers=[]
        )

    # ── VOD Watch Alert helpers ───────────────────────────────────────────────

    def get_vod_watch_alerts(self) -> list:
        """Return a copy of the VOD watch-alert rule list."""
        return list(self.vod_watch_alerts)

    def add_vod_watch_alert(self, rule: dict) -> None:
        """Add a watch-for rule (no-op if a rule with the same created id already exists)."""
        rule_id = rule.get("created", "")
        if rule_id and any(r.get("created") == rule_id for r in self.vod_watch_alerts):
            return
        # Carry both tracking keys from creation so a freshly-added rule is never
        # mistaken for a pre-feature rule by ``_migrate_vod_alert_viewed`` (which
        # seeds only rules that LACK ``viewed_ids``).  New matches recorded later
        # land in ``alerted_ids`` only → they read as unviewed (green).
        rule = dict(rule)
        rule.setdefault("alerted_ids", [])
        rule.setdefault("viewed_ids", [])
        self.vod_watch_alerts = list(self.vod_watch_alerts) + [rule]
        self.save()

    def remove_vod_watch_alert(self, rule_created: str) -> None:
        """Remove the rule with the given ``created`` timestamp id."""
        self.vod_watch_alerts = [
            r for r in self.vod_watch_alerts
            if r.get("created") != rule_created
        ]
        self.save()

    def record_vod_alert_match(self, rule_created: str, channel_id: str) -> None:
        """Append *channel_id* to the rule's ``alerted_ids`` list and save."""
        updated = []
        for r in self.vod_watch_alerts:
            if r.get("created") == rule_created:
                merged = dict(r)
                ids = list(merged.get("alerted_ids") or [])
                if channel_id not in ids:
                    ids.append(channel_id)
                merged["alerted_ids"] = ids
                updated.append(merged)
            else:
                updated.append(r)
        self.vod_watch_alerts = updated
        self.save()

    def baseline_vod_alert_matches(self, rule_created: str, channel_ids: list) -> int:
        """Record *channel_ids* as matches the user has ALREADY seen — one save.

        A watch-for rule is forward-looking: the dialog that creates it is
        headed "Watch for new content" and promises an alert "when matching
        content ... APPEARS on any of your sources". Everything already in the
        catalogue when the rule is written is not news, so it is written into
        both ``alerted_ids`` (the dedup set — it must never re-alert) and
        ``viewed_ids`` (the unviewed/green set — it must not badge). The rule
        then fires only on titles that turn up later.

        The backlog stays one click away: a rule's own "View matches" action
        already searches the catalogue for its keyword, so baselining hides
        nothing the user cannot ask for.

        Writes both lists and saves ONCE, rather than the per-match
        record-and-save loop, which cost one full config write per match (102
        of them for a single "Evil Dead" rule on a large library).

        Args:
            rule_created: The rule's ``created`` id.
            channel_ids: Every channel currently matching the rule.

        Returns:
            The number of ids baselined.
        """
        ids = list(dict.fromkeys(channel_ids))
        if not ids:
            return 0
        updated = []
        n = 0
        for r in self.vod_watch_alerts:
            if r.get("created") != rule_created:
                updated.append(r)
                continue
            merged = dict(r)
            alerted = list(merged.get("alerted_ids") or [])
            viewed = list(merged.get("viewed_ids") or [])
            for cid in ids:
                if cid not in alerted:
                    alerted.append(cid)
                if cid not in viewed:
                    viewed.append(cid)
            merged["alerted_ids"] = alerted
            merged["viewed_ids"] = viewed
            n = len(ids)
            updated.append(merged)
        self.vod_watch_alerts = updated
        if n:
            self.save()
        return n

    def get_vod_alert_matches(self, rule_created: str) -> list[str]:
        """Return the list of alerted channel ids for a given rule."""
        for r in self.vod_watch_alerts:
            if r.get("created") == rule_created:
                return list(r.get("alerted_ids") or [])
        return []

    # ── Per-match "viewed" state — single source of truth for the alert green ──
    # A channel is an UNVIEWED match iff it is in some rule's ``alerted_ids`` and not
    # in that rule's ``viewed_ids``.  Every alert-visibility surface (sidebar badge,
    # details Alert button, channel-list rows, Watch Queue line) reads this, so
    # clearing a match turns the green off everywhere at once.

    def get_unviewed_vod_match_ids(self) -> set[str]:
        """Return the set of channel ids that are matched but not yet viewed.

        Computed across every rule: ``⋃ alerted_ids − ⋃ viewed_ids``.
        """
        alerted: set[str] = set()
        viewed: set[str] = set()
        for r in self.vod_watch_alerts:
            alerted.update(r.get("alerted_ids") or [])
            viewed.update(r.get("viewed_ids") or [])
        return alerted - viewed

    def get_unviewed_vod_match_count(self) -> int:
        """Number of distinct unviewed matched channels across all rules."""
        return len(self.get_unviewed_vod_match_ids())

    def is_vod_match_unviewed(self, channel_id: str) -> bool:
        """True when *channel_id* is a matched-but-not-yet-viewed alert channel."""
        return channel_id in self.get_unviewed_vod_match_ids()

    def get_rules_with_new_matches_count(self) -> int:
        """Number of watch-for RULES that currently have >=1 unviewed match.

        Distinct from :meth:`get_unviewed_vod_match_count` (which counts matched
        *items*): this counts firing *alerts* for the header glance, so a single
        rule with 73 new items still reads as one firing alert.
        """
        return sum(
            1 for r in self.vod_watch_alerts
            if self.get_vod_rule_unviewed_count(r.get("created", "")) > 0
        )

    def get_vod_rule_unviewed_count(self, rule_created: str) -> int:
        """Number of unviewed matches for a single rule (sidebar per-rule badge)."""
        for r in self.vod_watch_alerts:
            if r.get("created") == rule_created:
                alerted = set(r.get("alerted_ids") or [])
                viewed = set(r.get("viewed_ids") or [])
                return len(alerted - viewed)
        return 0

    def mark_vod_alert_match_viewed(self, channel_id: str) -> bool:
        """Mark a single matched channel as viewed across every rule.

        Args:
            channel_id: The matched ChannelDB id to acknowledge.

        Returns:
            True if any rule changed (and the config was saved), else False.
        """
        changed = False
        updated = []
        for r in self.vod_watch_alerts:
            alerted = r.get("alerted_ids") or []
            viewed = list(r.get("viewed_ids") or [])
            if channel_id in alerted and channel_id not in viewed:
                merged = dict(r)
                viewed.append(channel_id)
                merged["viewed_ids"] = viewed
                updated.append(merged)
                changed = True
            else:
                updated.append(r)
        if changed:
            self.vod_watch_alerts = updated
            self.save()
        return changed

    def mark_all_vod_alerts_viewed(self) -> int:
        """Mark every matched channel as viewed (bulk "Clear Alerts").

        Returns:
            The count of distinct channels that were unviewed before the call
            (i.e. how many alerts the bulk-clear acknowledged).
        """
        before = self.get_unviewed_vod_match_count()
        if before == 0:
            return 0
        updated = []
        for r in self.vod_watch_alerts:
            merged = dict(r)
            # viewed = every alerted id (preserve order, dedup).
            merged["viewed_ids"] = list(dict.fromkeys(merged.get("alerted_ids") or []))
            updated.append(merged)
        self.vod_watch_alerts = updated
        self.save()
        return before

    def mark_vod_rule_viewed(self, rule_created: str) -> int:
        """Acknowledge every match for a single rule (per-rule "Clear this alert").

        Sets the matching rule's ``viewed_ids`` to all of its ``alerted_ids``
        (order-preserving dedup) and saves; other rules are left untouched.

        Args:
            rule_created: The ``created`` id of the rule to acknowledge.

        Returns:
            The number of channels that were unviewed for this rule before the
            call (how many alerts this clear acknowledged); 0 when the rule is
            unknown or already fully viewed (no save in that case).
        """
        cleared = self.get_vod_rule_unviewed_count(rule_created)
        if cleared == 0:
            return 0
        updated = []
        for r in self.vod_watch_alerts:
            if r.get("created") == rule_created:
                merged = dict(r)
                # viewed = every alerted id (preserve order, dedup).
                merged["viewed_ids"] = list(dict.fromkeys(merged.get("alerted_ids") or []))
                updated.append(merged)
            else:
                updated.append(r)
        self.vod_watch_alerts = updated
        self.save()
        return cleared

    def _migrate_vod_alert_viewed(self) -> None:
        """One-time per-rule seed: pre-feature rules treat existing matches as viewed.

        A rule that LACKS the ``viewed_ids`` key predates the alert-visibility
        feature; its ``alerted_ids`` were already toasted, so seed
        ``viewed_ids = alerted_ids`` to avoid a flood of green on first upgrade.
        Only matches recorded AFTER the upgrade (which append to ``alerted_ids``
        only) then light up.  Idempotent — once the key exists the rule is skipped.
        """
        changed = False
        updated = []
        for r in self.vod_watch_alerts:
            if "viewed_ids" not in r:
                merged = dict(r)
                merged["viewed_ids"] = list(merged.get("alerted_ids") or [])
                updated.append(merged)
                changed = True
            else:
                updated.append(r)
        if changed:
            self.vod_watch_alerts = updated
