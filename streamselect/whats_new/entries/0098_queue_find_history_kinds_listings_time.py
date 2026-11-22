from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=98,
    version="1.2.0",
    date="2026-11-22",
    title="History can hide live channels; Sports says how old its listings are",
    items=(
        "Watch Queue's \"Find in queue…\" box stays at the top of the section however the "
        "queue is scrolled, including with the scroll bar.",
        "History's ⋯ menu can show or hide Live channels, Movies and Series. The choice is "
        "remembered, and History says what it is leaving out.",
        "\"Still watching?\" after an autoplayed run also asks about the episode the run "
        "started with: untick \"I watched the first episode, too\" and it goes back to "
        "unwatched.",
        "Sports shows when its listings were last refreshed (\"Listings from 4:01 PM\") under "
        "the sort row, with a Refresh that fetches the live listings of your sources now. A "
        "refresh that fails says so.",
        "Scrolling the Sports list right after it redraws is no longer undone a moment later.",
    ),
    test_steps=(
        "Open Watch Queue's find box (the 🔍 in its header) on a long queue and drag the "
        "section's scroll bar to the bottom: the find box stays in view at the top.",
        "In History's ⋯ menu untick Live channels: live entries disappear, the group counts "
        "drop, and the list starts with \"Live channels hidden\". Restart the app: still "
        "hidden. Tick it again: they come back.",
        "Autoplay through two episodes of a season, close the player, untick \"I watched the "
        "first episode, too\" and answer: the first episode shows as unwatched in the season.",
        "Open Sports: under the sort row it reads \"Listings from <time>\". Click Refresh: it "
        "reads \"Refreshing listings…\", then the new time once the sources finish.",
        "With the Sports list scrolled down, open a game's channels and scroll straight "
        "away: the list stays where you scrolled.",
    ),
)
