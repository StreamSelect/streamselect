from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=24,
    version="1.0.2",
    date="2026-11-12",
    title="Sports says it is finding games instead of showing none",
    items=(
        "Opened right after the app starts, Sports showed no games until the first search "
        "of your channel listings finished, then the games appeared. It now says it is "
        "finding games, starts that search at once if it had not begun, and shows the "
        "games when it is done.",
    ),
    test_steps=(
        "Restart the app and open Sports within a few seconds: it says \"Finding games in "
        "your channel listings…\", never On now 0, then the games appear.",
        "With Sports open, refresh a source: a \"Looking for new games…\" line shows under "
        "On now while the games are re-found, and the cards stay on screen.",
    ),
)
