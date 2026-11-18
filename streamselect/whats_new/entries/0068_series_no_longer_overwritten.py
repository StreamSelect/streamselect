from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=68,
    version="1.0.6",
    date="2026-11-17",
    title="Series no longer disappear behind a live channel with the same number",
    items=(
        "A source numbers its series separately from its live channels and movies. StreamSelect "
        "treated a series and a live channel with the same number as one channel, so a series "
        "could be skipped as a duplicate or replaced by the live channel on the next refresh: a "
        "queued \"Jeeves And Wooster\" turned into \"TNT HD\". Each is now its own channel.",
        "Series that were missing come back after the next full refresh of their source, and a "
        "Watch Queue item that had turned into a live channel points at its series again.",
        "Copied channel ids keep working. A channel added from now on has an id that names its "
        "type, such as …_series-25529.",
    ),
    test_steps=(
        "Refresh a source fully (not live channels only): the log no longer says \"dropped 2,074 "
        "duplicate channel IDs\"; at most a few channels listed more than once are dropped.",
        "Search for a series that was missing before and is now found; open it and copy its id "
        "from the source chip: it ends in _series-<number>, and pasting it into search finds it.",
        "A Watch Queue item that showed as a live channel (or was marked unavailable) now shows "
        "its series and plays it; the log says \"Watch queue: … moved back to its series row\".",
    ),
)
