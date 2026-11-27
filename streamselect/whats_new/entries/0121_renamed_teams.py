from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=121,
    version="1.3.0",
    date="2026-11-27",
    title="A renamed team is one team",
    items=(
        "Listings that still use a team's old name are read as the team today: the Utah "
        "Hockey Club is the Utah Mammoth, so the NHL's teams list it once and a game listed "
        "under the old name joins the Mammoth's game.",
    ),
    test_steps=(
        "Start the app and wait for the Sports view to find today's games.",
        "Tools ▸ Library Breakdown ▸ Sports ▸ Hockey ▸ NHL: \"Utah Mammoth\" is listed and "
        "\"Utah Hockey Club\" is not.",
    ),
)
