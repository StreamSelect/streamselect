"""One-time migrations of stored settings, as methods on ``Config``.

Split out of ``config.py`` (ledger F68): each method rewrites an old stored
value into its current form once (usually version-gated) and is called from
``Config.model_post_init`` / ``load``. They are behaviour, not settings, so
they live beside the settings register rather than in it. ``Config`` inherits
this mixin; the methods keep their names, so callers and tests are unchanged.
"""

from __future__ import annotations

from loguru import logger

from streamselect.core.catalog_refresh import RETIRED_LIVE_REFRESH_MODES


class _ConfigMigrationsMixin:
    """The ``_migrate_*`` / ``_inject_*`` / ``_retire_*`` steps ``Config`` runs on load."""

    def _migrate_metadata_enabled_providers(self) -> None:
        """Merge newly-shipped provider names into ``metadata_enabled_providers`` — ONCE.

        ``metadata_enabled_providers`` has no Settings UI (nothing ever writes it), so
        a persisted value missing a shipped provider name only ever means "this config
        predates that provider" — there is no user intent to preserve. Without this, an
        existing install's persisted ``["provider"]`` value silently excludes "tmdb"/
        "omdb" from ``MetadataProviderRegistry.get_enabled()`` forever: pasting a TMDb
        API key into Settings becomes a silent no-op with nothing to diagnose from
        (user-reported against a real ``config.yaml``, wave4/external-metadata-providers).

        Version-gated (``metadata_enabled_providers_version``) rather than a plain
        membership check re-run on every load, so that if this list ever grows an
        editing UI, a user's later, deliberate removal of a provider is never silently
        undone by this migration running again on a subsequent launch. Idempotent:
        a no-op once the version is already >= 1.
        """
        if self.metadata_enabled_providers_version >= 1:
            return
        for name in ("tmdb", "omdb"):
            if name not in self.metadata_enabled_providers:
                self.metadata_enabled_providers.append(name)
        self.metadata_enabled_providers_version = 1

    def _retire_collapsed_shelves(self) -> None:
        """Drop the stored collapsed zone, once, preserving what it implied.

        ``discover_collapsed_shelves`` recorded the DEFAULT zone — the value
        ``determine_zone`` falls through to — so every entry was the answer the
        code would give with no entry at all. On a user's config that was
        818 of many lines.

        The one thing it did carry is that the user had been here before, which
        ``_is_first_launch`` read as "not all four lists are empty". That
        meaning is transferred to ``discover_zones_seeded`` first, then the list
        is cleared. Order matters: clearing first would erase the evidence this
        migration needs.
        """
        if self.discover_zones_seeded:
            return
        has_zone_state = any((self.discover_pinned_shelves,
                              self.discover_expanded_shelves,
                              self.discover_collapsed_shelves,
                              self.discover_hidden_shelves))
        changed = False
        if has_zone_state:
            self.discover_zones_seeded = True
            changed = True
        if self.discover_collapsed_shelves:
            logger.info(
                "Discover: dropping {} stored collapsed shelves — collapsed is "
                "the default zone, so they recorded nothing",
                len(self.discover_collapsed_shelves))
            self.discover_collapsed_shelves = []
            changed = True
        if changed:
            self.save()

    def _inject_new_sections(self) -> None:
        """Insert newly added sidebar sections into existing configs that predate them."""
        changed = False
        # "downloads"/"recordings" (Catch, Keep, Record slice 4): the engines
        # shipped in an earlier change with no surface at all, so an existing config has no
        # entry for either and would never show them.
        new_sections = ["queue", "recommended", "downloads", "recordings"]
        for sid in new_sections:
            if sid not in self.sidebar_sections:
                idx = self.sidebar_sections.index("alerts") + 1 if "alerts" in self.sidebar_sections else 0
                self.sidebar_sections.insert(idx, sid)
                changed = True
            if sid not in self.sidebar_visible_sections:
                idx = self.sidebar_visible_sections.index("alerts") + 1 if "alerts" in self.sidebar_visible_sections else 0
                self.sidebar_visible_sections.insert(idx, sid)
                changed = True
        # Retire orphaned sections whose UI no longer exists in the sidebar section
        # stack — strip any stale saved reference so the create loop never tries to
        # build a section that no longer exists:
        #   "new_episodes" — folded into the always-visible Watch Alerts section.
        #   "sources"      — moved out of the sidebar entirely (Wave 6) into the
        #                    status strip + Sources manager view.
        _retired_sections = {"new_episodes", "sources"}
        for _attr in ("sidebar_sections", "sidebar_visible_sections"):
            _lst = getattr(self, _attr)
            _filtered = [s for s in _lst if s not in _retired_sections]
            if _filtered != _lst:
                setattr(self, _attr, _filtered)
                changed = True
        if changed:
            self.save()

    def _apply_value_migrations(self) -> None:
        """Field migrations that must run over the values, wherever they came from.

        Separated from ``model_post_init`` because these two touch PROFILE
        fields, which no longer arrive only from YAML: once
        ``profile_store.attach`` loads a stored value over the top, a migration
        that ran only at construction would never see it. So attach calls this
        again.

        Both are gated on emptiness and are idempotent — that is the property
        that lets them run twice, and it is what this split relies on.

        Not moved here: the ``filter_config_version < 1`` migration in
        ``model_post_init``, which also touches profile fields. It is gated on a
        version marker that is set to 1 by the first save any config has ever
        done, so it is already a no-op for everyone whose data can reach the
        store — a pre-sentinel ``[]`` is migrated to ``None`` before it is ever
        written there. Its marker stays in ``config.yaml`` on purpose: a
        migration's own bookkeeping belongs with the code that decides whether
        to run it, not inside the data it rewrites.
        """
        # Seed per-match "viewed" state on pre-feature VOD watch-alert rules so the
        # alert-visibility green only lights up for matches found AFTER the upgrade.
        self._migrate_vod_alert_viewed()
        # Each of these rewrites a value an EXISTING config.yaml already has
        # written down, which moving a default cannot reach. See each method's
        # docstring for why rewriting that particular one is legitimate.
        self._migrate_metadata_enabled_providers()
        self._migrate_background_polling_defaults()
        self._migrate_live_refresh_mode()
        self._migrate_content_types_to_categories()

    def _migrate_content_types_to_categories(self) -> None:
        """Carry the retired hand-typed Content Types onto channel categories.

        The old list matched 28 exact provider header spellings; the
        ``category`` tag says what a channel IS whatever the provider calls it.
        A group name that is also a category (Kids, Religious, Sports, News)
        carries over; the rest (Entertainment, Movies, Relaxation, and raw
        header labels) have no category and are dropped. Gated on the old lists
        being non-empty, so it runs once and is idempotent.
        """
        from streamselect.core.content_labels import CONTENT_DESCRIPTOR_GROUPS

        old = list(self.global_filter_excluded_content_types or [])
        raw = list(self.global_filter_excluded_source_categories or [])
        if not old and not raw:
            return
        carried = [n for n in old if n in CONTENT_DESCRIPTOR_GROUPS]
        dropped = [n for n in old if n not in CONTENT_DESCRIPTOR_GROUPS] + raw
        cats = list(self.global_filter_excluded_channel_categories or [])
        self.global_filter_excluded_channel_categories = cats + [n for n in carried if n not in cats]
        self.global_filter_excluded_content_types = []
        self.global_filter_excluded_source_categories = []
        if dropped:
            logger.info(f"Exclusions: retired content types with no channel category: {dropped}")

    #: What ``tmdb_enrichment_session_cap`` and ``series_monitor_interval_minutes``
    #: defaulted to before they were turned off. A stored value EQUAL to one of
    #: these is the old default persisted, not a choice — see the migration.
    _POLLING_OLD_DEFAULTS = {
        "tmdb_enrichment_session_cap": 500,
        "series_monitor_interval_minutes": 1440,
    }

    def _migrate_background_polling_defaults(self) -> None:
        """Apply the new OFF defaults to a config that already stored the old ones.

        The defect this exists for: changing a pydantic default fixes nothing
        for an existing user. ``config.save()`` writes every field, so the
        a user's ``config.yaml`` carries ``tmdb_enrichment_session_cap: 500``
        explicitly — and an explicit stored value beats any default. They
        watched the genre backfill keep running (``filled 40 of 40 movie(s)``
        every ~6 s) while looking at a PR whose entire subject was turning it
        off.

        Because ``save()`` persists every field, a stored value is
        indistinguishable from a default nobody ever chose — the same argument
        ``_migrate_metadata_enabled_providers`` makes, and why rewriting one is
        legitimate here.

        **Only a value equal to the OLD DEFAULT is rewritten.** That is the
        conservative half: 500 and 1440 are provably "the old default, written
        down by save()", while any other number is something a person typed and
        is left alone. A user who deliberately set 720 keeps 720.

        Version-gated so it runs once: turning polling back on later must stick,
        and a migration re-running every launch would quietly undo it — the trap
        every version marker in this file exists to avoid.
        """
        if self.background_polling_off_version >= 1:
            return
        for field, old_default in self._POLLING_OLD_DEFAULTS.items():
            if getattr(self, field, None) == old_default:
                setattr(self, field, 0)
                logger.info(
                    "Config migration: {} was {} (the old default, not a choice) "
                    "— turned off", field, old_default)
        self.background_polling_off_version = 1

    def _migrate_live_refresh_mode(self) -> None:
        """Rewrite a stored ``live_refresh_mode`` naming a retired option — ONCE.

        Same argument as the method above (``save()`` writes every field, so an
        explicit stored value beats any default), and the same version gate.
        What makes it necessary rather than tidy: ``SettingsDialog._load_values``
        falls back to ``findData("manual")`` for a value the combo cannot show,
        so without this the dialog would DISPLAY "Manual" while the file still
        said otherwise, silently, until the next Save. The retired-value map is
        ``catalog_refresh.RETIRED_LIVE_REFRESH_MODES`` — one module owns the mode
        vocabulary.
        """
        if self.live_refresh_mode_version >= 1:
            return
        replacement = RETIRED_LIVE_REFRESH_MODES.get(self.live_refresh_mode)
        if replacement is not None:
            logger.info("Config migration: live_refresh_mode was {!r}, an option "
                        "retired with the Sports and Events views — now {!r}",
                        self.live_refresh_mode, replacement)
            self.live_refresh_mode = replacement
        self.live_refresh_mode_version = 1

    def _migrate_qa_step_results(self) -> None:
        """Backfill ``qa_step_results`` from the legacy ``qa_checked_steps`` list shape.

        Idempotent: a no-op once ``qa_step_results`` is populated.  Each previously
        checked step index becomes a ``{"state": "pass", "sha": "", "ts": ""}`` record.
        Tolerates both the historical list form (``{eid: [idx, ...]}``) and a
        dict-of-bools form (``{eid: {idx: bool}}``) in case an old variant exists.
        """
        if self.qa_step_results or not self.qa_checked_steps:
            return
        migrated: dict = {}
        for entry_id, checked in self.qa_checked_steps.items():
            indices: list[int] = []
            if isinstance(checked, dict):
                indices = [int(idx) for idx, on in checked.items() if on]
            elif isinstance(checked, (list, tuple, set)):
                indices = [int(idx) for idx in checked]
            if not indices:
                continue
            migrated[str(entry_id)] = {
                str(idx): {"state": "pass", "sha": "", "ts": ""}
                for idx in indices
            }
        if migrated:
            self.qa_step_results = migrated

    class Config:
        arbitrary_types_allowed = True
