from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=27,
    version="1.0.2",
    date="2026-11-13",
    title="Watched time no longer jumps to impossible lengths on live channels",
    items=(
        "A live channel's own clock can jump, and the app counted the jump as time watched: "
        "one 15-minute game was stored as 26 hours. Watched time is now the real time a play "
        "ran, so source analytics' watch time and the channel a Sports card picks stay honest.",
    ),
    test_steps=(
        "Play a live sports channel for about two minutes, then stop it. Open the source's "
        "analytics: the play adds about two minutes of watch time, not hours.",
    ),
)
