from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=67,
    version="1.0.6",
    date="2026-11-17",
    title="The tray shows a live game right after launch",
    items=(
        "When a game you set an alert for is already on as StreamSelect starts, the tray icon "
        "turns green straight away instead of 20-30 seconds later. Newly found games are "
        "checked against your alerts as soon as they come in, too.",
    ),
    test_steps=(
        "With an alerted game on, quit StreamSelect and start it again: the tray icon is the "
        "green logo within a couple of seconds of the window appearing, and the tray menu "
        "lists the game.",
    ),
)
