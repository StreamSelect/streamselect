from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=95,
    version="1.2.0",
    date="2026-11-22",
    title="Posters fill their space; the tray follows a finished game at once",
    items=(
        "A poster in the details pane now fills the full height of its space after the pane "
        "is widened, instead of staying small with empty bands above and below.",
        "Marking an alerted game finished (or still on) updates the tray icon and Watch "
        "Alerts straight away, instead of up to 30 seconds later. Adding or removing an "
        "alert bell does the same.",
    ),
    test_steps=(
        "Narrow the details pane, select a film or series with a poster, then widen the "
        "pane: the poster grows to the full height of the grey box, with no bands above "
        "and below.",
        "With an alerted game live (tray icon showing a live game), mark the game finished "
        "on its card in Sports: the tray icon goes back to normal within a second or two.",
        "Right-click the finished game and choose \"Not finished — still on\": the tray "
        "shows it live again straight away.",
    ),
)
