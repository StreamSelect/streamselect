from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=12,
    version="1.0.1",
    date="2026-11-11",
    title="Scheduled live refreshes do only live work",
    items=(
        "The refresh notification now says whether it covers live channels only or live, "
        "movies and series.",
        "A scheduled live-channel refresh re-read every movie and series afterwards. It now "
        "processes only the live channels, so it finishes sooner.",
        "A live-channel refresh no longer counts as a full refresh, so a source set to refresh "
        "weekly gets its movies and series updated again.",
        "The TV guide is no longer downloaded twice within minutes after launch, or after every "
        "live-channel refresh. It is downloaded when its own refresh interval says so.",
    ),
    test_steps=(
        "With Settings set to refresh live channels on a schedule, wait for the next live "
        "refresh: the notification title ends in \"(live channels only)\".",
        "Click Refresh on a source: the notification title ends in \"(live, movies and series)\".",
        "Relaunch the app and wait 10 minutes: the TV guide downloads at most once.",
    ),
)
