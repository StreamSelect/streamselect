"""Analytics repository: what each source carries that the others do not.

Feeds the Sources editor's Analytics tab. "The same title" is the stored
``content_key`` — the identity Browse, Discover and Other Versions already
collapse on (DR-0009/DR-0011) — for live channels, films and series alike.
"""

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from streamselect.core.database import ChannelDB, EpgProgramDB, EpisodeDB, ProviderDB
from streamselect.core.playback_models import PlaybackEventDB
from streamselect.core.repositories.dtos import (
    AnalyticsSourceDTO,
    CatalogueMixDTO,
    GuideCoverageDTO,
    PrefixStatDTO,
    ServerAddressDTO,
    TitleOverlapDTO,
    ViewingDTO,
)
from streamselect.core.content_identity import title_key_expr
from streamselect.core.prefix_vocabulary import is_known_prefix

_SAMPLE_NAMES = 5
#: The order the unknown-prefix list groups media types in.
_PREFIX_MEDIA_ORDER = ("live", "movie", "series")

#: Most-played titles a source's Viewing section names.
TOP_TITLES = 10
#: "Played recently" window for What you watch here.
RECENT_DAYS = 30

#: One title per content_key; a row without one is its own title.
_TITLE_KEY = title_key_expr(ChannelDB.content_key, ChannelDB.id)


class AnalyticsRepository:
    """Compute source analytics: title overlap, guide coverage, addresses, prefixes."""

    def __init__(self, session: Session):
        self.session = session

    def title_overlap(self) -> TitleOverlapDTO:
        """Titles per source, the ones only it carries, and what each pair shares.

        One scan for every source at once: grouping on ``content_key`` in SQL
        took ~30 s on a 785k-row library (two self-joins); collecting the
        holders of each key in Python takes ~1.4 s and answers every source
        and every pair from the same pass, so the tab can cache it per session.
        A row with no ``content_key`` is its own title (``'id:' || id``, the
        rule every collapse surface uses), so it is always only-here.

        Disabled and expired sources are included — the source you are about
        to delete is exactly the one whose numbers you want (user report, Q9).
        Channels whose source no longer exists are not (ledger F60).
        """
        now = datetime.now()
        sources = tuple(
            AnalyticsSourceDTO(
                id=p.id, name=p.name, is_active=bool(p.is_active),
                is_expired=bool(p.account_exp_date and p.account_exp_date <= now),
            )
            for p in self.session.query(ProviderDB).order_by(ProviderDB.name)
        )
        known = [s.id for s in sources]
        rows = self.session.execute(
            select(ChannelDB.id, ChannelDB.provider_id, ChannelDB.media_type, ChannelDB.content_key)
            .where(ChannelDB.provider_id.in_(known))
        ).all()

        holders: dict[tuple, set] = defaultdict(set)
        for _cid, pid, media, key in rows:
            if key is not None:
                holders[(media, key)].add(pid)

        totals: dict[tuple, int] = defaultdict(int)
        only: dict[tuple, int] = defaultdict(int)
        shared: dict[tuple, int] = defaultdict(int)
        for (media, _key), pids in holders.items():
            for pid in pids:
                totals[(pid, media)] += 1
                if len(pids) == 1:
                    only[(pid, media)] += 1
                    continue
                for other in pids:
                    if other != pid:
                        shared[(pid, other, media)] += 1

        only_ids: dict[str, set] = defaultdict(set)
        for cid, pid, media, key in rows:
            if key is None:
                totals[(pid, media)] += 1
                only[(pid, media)] += 1
                only_ids[pid].add(cid)
            elif len(holders[(media, key)]) == 1:
                only_ids[pid].add(cid)

        return TitleOverlapDTO(
            sources=sources, totals=dict(totals), only=dict(only), shared=dict(shared),
            only_ids={pid: frozenset(ids) for pid, ids in only_ids.items()},
        )

    def guide_coverage(self, provider_id: str) -> GuideCoverageDTO:
        """How many of a source's live channels show guide data, and how far ahead.

        Counted from the CHANNEL side — a programme matched to this source's
        channel, from any feed. Counting the source's own feed instead measures
        something else: on a large library one source's feed is matched to many
        channels, many of them on other sources, while 493 of its own
        many live channels have a guide.
        """
        live = self.session.query(ChannelDB.id).filter(
            ChannelDB.provider_id == provider_id, ChannelDB.media_type == "live")
        total = live.count()
        matched = self.session.query(
            func.count(func.distinct(EpgProgramDB.channel_db_id)), func.max(EpgProgramDB.stop_time)
        ).filter(EpgProgramDB.channel_db_id.in_(live.subquery().select())).one()
        return GuideCoverageDTO(live_channels=total, with_guide=matched[0] or 0, guide_until=matched[1])

    def server_addresses(self, provider_id: str) -> list[ServerAddressDTO]:
        """Each address's recent success rate and typical speed, best first.

        Reads the stored attempt history (``recent_attempts``, the last ~20
        requests per address), falling back to the lifetime counts for an
        address recorded before that history existed. Carries that history
        in order, the last success, and which address ``UrlCycler`` would
        try first (Q22).
        """
        from streamselect.core.repositories.provider import ProviderRepository

        row = self.session.query(ProviderDB).filter_by(id=provider_id).first()
        if row is None:
            return []
        from streamselect.core.url_cycle import UrlCycler

        model = ProviderRepository(self.session).to_model(row)
        first = (UrlCycler(model, "analytics").first_choice() or "").rstrip("/")
        out = []
        for pu in model.urls:
            recent = sorted((a for a in pu.recent_attempts if a.host_at_fault or a.success),
                            key=lambda a: a.timestamp)
            if recent:
                tried, worked = len(recent), sum(1 for a in recent if a.success)
            else:
                tried, worked = pu.success_count + pu.failure_count, pu.success_count
            out.append(ServerAddressDTO(
                url=pu.url, tried=tried, worked=worked,
                median_latency_ms=pu.median_latency_ms() or None,
                history=tuple(a.success for a in recent), last_worked=pu.last_success,
                in_use=bool(first) and pu.url.rstrip("/") == first,
            ))
        out.sort(key=lambda a: (-(a.worked / a.tried if a.tried else -1), a.median_latency_ms or 10**9))
        return out

    def viewing(self, provider_id: str) -> ViewingDTO:
        """What has been watched from *provider_id*, read from the play log.

        Everything but favourites comes from ``playback_events``, never from
        the History columns (``ChannelDB.play_count``/``last_played``):
        clearing History zeroed those and took the analytics with it, an
        episode's plays never reached them, and a live event channel is renamed
        for each new game, so its count named something never watched. A film
        or series is one title by its title key, an episode counts for its
        series, and a live channel keeps the name it had when it was played.
        """
        from streamselect.core.epg_utils import now_utc

        seconds, since = self.session.query(
            func.sum(PlaybackEventDB.seconds_watched), func.min(PlaybackEventDB.started_at),
        ).filter(PlaybackEventDB.provider_id == provider_id, PlaybackEventDB.channel_id != "").one()
        events = self.session.query(
            PlaybackEventDB.channel_id, PlaybackEventDB.title, PlaybackEventDB.started_at,
            PlaybackEventDB.seconds_watched,
        ).filter(PlaybackEventDB.provider_id == provider_id, PlaybackEventDB.channel_id != "",
                 PlaybackEventDB.outcome == "started").all()     # "": forgotten with History
        ids = {cid for cid, *_ in events}
        series = dict(self.session.query(EpisodeDB.id, ChannelDB.id).join(
            ChannelDB, (ChannelDB.provider_id == EpisodeDB.provider_id)
            & (ChannelDB.source_id == EpisodeDB.series_id) & (ChannelDB.media_type == "series"),
        ).filter(EpisodeDB.id.in_(ids))) if ids else {}
        title = func.coalesce(ChannelDB.detected_title, ChannelDB.name)
        rows = {cid: (name, media or "", key, ck) for cid, name, media, key, ck in self.session.query(
            ChannelDB.id, title, ChannelDB.media_type, _TITLE_KEY, ChannelDB.content_key,
        ).filter(ChannelDB.id.in_(ids | set(series.values())))} if ids else {}
        groups: dict[tuple, list] = {}     # [name, media, plays, last, title key, seconds, content key]
        for cid, raw, when, secs in events:
            owner = series.get(cid, cid)
            name, media, key, ck = rows.get(owner, (raw, "", f"id:{owner}", None))
            by_name = media in ("live", "")
            group = groups.setdefault((key, raw) if by_name else (key,),
                                      [raw if by_name else name, media, 0, when, key, 0, ck])
            group[2] += 1
            group[3] = max(group[3], when)
            group[5] += secs or 0
        keys = {g[6] for g in groups.values() if g[6]}
        elsewhere = {k for (k,) in self.session.query(ChannelDB.content_key).filter(
            ChannelDB.provider_id != provider_id, ChannelDB.content_key.in_(keys)).distinct()} if keys else set()
        by_media: dict[str, int] = defaultdict(int)
        for g in groups.values():
            if g[1]:
                by_media[g[1]] += 1
        cutoff = now_utc() - timedelta(days=RECENT_DAYS)
        ranked = sorted(groups.values(), key=lambda g: (-g[2], -g[3].timestamp()))
        favourites = self.session.query(func.count(func.distinct(_TITLE_KEY))).filter(
            ChannelDB.provider_id == provider_id, ChannelDB.is_favorite.is_(True)).scalar()
        played_episodes = ids & set(series)
        return ViewingDTO(
            titles=len(groups), plays=len(events),
            last_played=max((g[3] for g in groups.values()), default=None), by_media=dict(by_media),
            top=tuple(tuple(g[:6]) for g in ranked[:TOP_TITLES]),
            seconds_watched=int(seconds or 0), watched_since=since,
            only_here=sum(1 for g in groups.values() if g[6] is None or g[6] not in elsewhere),
            recent=sum(1 for g in groups.values() if g[3] >= cutoff), favourites=favourites or 0,
            episodes=len(played_episodes), episode_series=len({series[e] for e in played_episodes}),
        )

    def title_channel_ids(self, provider_id: str, title_key: str) -> frozenset[str]:
        """Channel ids on *provider_id* carrying one title (a ``_TITLE_KEY``
        value from :meth:`viewing`'s Most played) — what a click hands to Search."""
        return frozenset(i for (i,) in self.session.query(ChannelDB.id).filter(
            ChannelDB.provider_id == provider_id, _TITLE_KEY == title_key))

    def region_channel_ids(self, provider_id: str, region: str) -> frozenset[str]:
        """Channel ids on *provider_id* whose detected region is *region* — the
        rows a Titles-by-region click hands to Search (the same predicate
        :meth:`catalogue_mix` counts by)."""
        return frozenset(i for (i,) in self.session.query(ChannelDB.id).filter(
            ChannelDB.provider_id == provider_id, ChannelDB.detected_region == region))

    def catalogue_mix(self, provider_id: str) -> CatalogueMixDTO:
        """Titles per detected region on *provider_id*, largest first.

        Region is the axis these sources sort by: the provider's own
        ``language`` field is empty on every source in a large library,
        and a region code ("FR", "IN") is how the catalogues label language.
        """
        rows = self.session.query(ChannelDB.detected_region, func.count(func.distinct(_TITLE_KEY))) \
            .filter(ChannelDB.provider_id == provider_id).group_by(ChannelDB.detected_region).all()
        unknown = sum(n for code, n in rows if not code)
        regions = tuple(sorted(((code, n) for code, n in rows if code), key=lambda r: (-r[1], r[0])))
        return CatalogueMixDTO(regions=regions, unknown=unknown,
                               total=unknown + sum(n for _, n in regions))

    def unrecognized_prefixes(self, provider_id: str | None = None) -> list[PrefixStatDTO]:
        """Prefix tokens the parser does not know, per media type, with samples.

        "Known" is ``prefix_vocabulary.is_known_prefix`` — the same tables the
        parser reads, compounds included — not a lexicon of its own. One row
        per (prefix, media type), live first, then films, then series; most
        common first within each. Counted with GROUP BY and sampled with one
        windowed query, both scoped to *provider_id* (None = every source).
        """
        scope = [ChannelDB.detected_prefix.isnot(None), ChannelDB.detected_prefix != "",
                 ChannelDB.is_hidden.is_(False)]
        if provider_id:
            scope.append(ChannelDB.provider_id == provider_id)
        counts = [
            (prefix, media or "", n) for prefix, media, n in self.session.query(
                ChannelDB.detected_prefix, ChannelDB.media_type, func.count(ChannelDB.id)
            ).filter(*scope).group_by(ChannelDB.detected_prefix, ChannelDB.media_type)
            if not is_known_prefix(prefix)
        ]
        if not counts:
            return []
        order = {m: i for i, m in enumerate(_PREFIX_MEDIA_ORDER)}
        counts.sort(key=lambda c: (order.get(c[1], len(order)), -c[2], c[0]))

        rank = func.row_number().over(
            partition_by=(ChannelDB.detected_prefix, ChannelDB.media_type), order_by=ChannelDB.id)
        sampled = (
            select(ChannelDB.detected_prefix.label("prefix"), ChannelDB.media_type.label("media"),
                   ChannelDB.name.label("name"), rank.label("rn"))
            .where(*scope, ChannelDB.detected_prefix.in_({p for p, _, _ in counts}))
            .subquery()
        )
        samples: dict[tuple[str, str], list[str]] = defaultdict(list)
        for prefix, media, name in self.session.execute(
            select(sampled.c.prefix, sampled.c.media, sampled.c.name).where(sampled.c.rn <= _SAMPLE_NAMES)
        ):
            samples[(prefix, media or "")].append(name)

        return [
            PrefixStatDTO(prefix=prefix, count=n, sample_names=samples.get((prefix, media), []),
                          is_recognized=False, media_type=media)
            for prefix, media, n in counts
        ]
