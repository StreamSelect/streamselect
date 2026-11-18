from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=65,
    version="1.0.6",
    date="2026-11-17",
    title="Tray icon: alerts you can see at a glance",
    items=(
        "While a game you set an alert for is on, the whole tray icon turns into a green disc "
        "with the sports whistle, so it is obvious at tray size. The usual icon comes back when "
        "the game ends.",
        "The Watch Alert bell and the update arrow are bigger, and a thin gap now separates them "
        "from the icon, so they no longer blur into it.",
    ),
    test_steps=(
        "Set an alert on a game in Sports and wait until it starts (or open the app while one "
        "is on): the tray icon is a green disc with the whistle; the tray menu lists the game.",
        "When the game ends, the tray icon is the normal app icon again.",
        "With the window hidden, let a Watch Alert notification arrive: the tray icon shows a "
        "large bell in its lower-right corner with a gap around it; opening the tray menu "
        "clears it.",
    ),
)
