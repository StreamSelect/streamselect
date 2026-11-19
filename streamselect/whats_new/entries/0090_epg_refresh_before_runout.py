from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=90,
    version="1.1.0",
    date="2026-11-19",
    title="The TV guide refreshes before it runs out",
    items=(
        "Auto guide refresh now times itself by how far ahead your source's guide reaches. "
        "A guide that covers a day ahead refreshes about every 12 hours, instead of waiting "
        "until after it had run out.",
        "Whatever refresh interval you choose, the guide is also refreshed an hour before its "
        "last programme starts, so Watch Alerts never says the guide has run out while the "
        "app is running.",
        "The source editor's guide line says how far ahead the guide reaches and how often "
        "Auto refreshes it.",
    ),
    test_steps=(
        "Open a source in the source editor: the guide line reads \"Current — guide through … "
        "· Auto: guide reaches ~24h ahead → refreshing ~every 12h\" (your numbers).",
        "Leave the app running past the time the guide would have run out: Watch Alerts never "
        "shows \"Guide data has run out\".",
        "In the log, after a guide fetch: \"guide refresh before it runs out scheduled for …\" "
        "names a time an hour before the guide's last programme.",
    ),
)
