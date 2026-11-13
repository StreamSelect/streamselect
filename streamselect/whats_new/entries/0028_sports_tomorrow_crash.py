from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=28,
    version="1.0.2",
    date="2026-11-13",
    title="Opening a game that hasn't started no longer closes the app",
    items=(
        "Clicking one of tomorrow's games in Sports closed the app. It now opens the list of "
        "channels that will show the game, and clicking it again folds the list away.",
    ),
    test_steps=(
        "In Sports, click a game under Tonight or Tomorrow: its channel list opens beneath it "
        "and the app stays open. Click it again: the list folds away.",
    ),
)
