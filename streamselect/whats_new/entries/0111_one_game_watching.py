from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=111,
    version="1.3.0",
    date="2026-11-25",
    title="Sports: only the game on now says WATCHING",
    items=(
        "When one channel shows two games back to back, playing it marks only the game "
        "that is on now as WATCHING. The earlier game's card no longer says it too.",
    ),
    test_steps=(
        "Sports: find a channel listed for two games in a row (one likely ending, one on "
        "now) and play it: only the game on now says WATCHING; the earlier card shows its "
        "play line without the word.",
    ),
)
