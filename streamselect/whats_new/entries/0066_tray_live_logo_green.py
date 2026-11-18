from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=66,
    version="1.0.6",
    date="2026-11-17",
    title="Tray icon: the logo turns green while your game is on",
    items=(
        "While a game you set an alert for is on, the tray icon is the StreamSelect logo on "
        "green instead of a whistle, so it still looks like the app.",
    ),
    test_steps=(
        "Set an alert on a game in Sports and wait until it starts: the tray icon is the "
        "S-arrow logo on a green square with rounded corners; when the game ends it is the "
        "usual logo again.",
    ),
)
