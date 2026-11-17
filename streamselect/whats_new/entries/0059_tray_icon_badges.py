from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=59,
    version="1.0.6",
    date="2026-11-16",
    title="Gentler tray icon badges, and one for a game on now",
    items=(
        "The tray icon no longer shows a red \"!\" for a new alert. It shows a small bell on a "
        "soft lavender disc instead, the same bell as Watch Alerts.",
        "While a game you set an alert on is live, the tray icon shows the Sports whistle on a "
        "green disc, and it stays there until the game ends.",
        "When the only news is a new version of StreamSelect, the icon shows an up arrow on a "
        "blue disc, so an update never looks like an alert.",
    ),
    test_steps=(
        "Hide the app to the tray and wait for a Watch Alert notification: the tray icon gets a "
        "bell on a lavender disc. Open the tray menu: the badge goes away.",
        "Set an alert on a game and let it start: the tray icon shows a whistle on a green disc. "
        "Open the menu or the window: the whistle stays until the game is over.",
        "With an update available and no other alerts, hide the app to the tray: the update "
        "notification leaves an up arrow on a blue disc.",
    ),
)
