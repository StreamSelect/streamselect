from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=91,
    version="1.1.0",
    date="2026-11-19",
    title="Sports: the list stays put when you change something",
    items=(
        "Making a channel PREFERRED no longer makes the Sports list jump. The list stays "
        "where you scrolled it, and the open channel list keeps its order until you close "
        "it; the game's play button switches to your preferred channel straight away.",
        "The list also stays where you scrolled it when it updates itself each minute.",
    ),
    test_steps=(
        "Open Sports, scroll down, open a game's channel list and click PREFERRED on a "
        "channel near the bottom: the list doesn't move and the row stays under the pointer.",
        "Close and reopen that list: the preferred channel is now first.",
        "Scroll part way down and wait a minute: the list stays where it was.",
    ),
)
