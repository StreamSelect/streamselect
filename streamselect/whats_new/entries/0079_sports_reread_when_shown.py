from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=79,
    version="1.0.7",
    date="2026-11-18",
    title="Sports: new games found while you're elsewhere show up when you come back",
    items=(
        "If Sports finished looking for games while it wasn't on screen, it now reads the "
        "results as soon as it is shown again, including the league order by what you watch.",
    ),
    test_steps=(
        "Start the app, open Sports, then switch to another view before \"Looking for new "
        "games…\" disappears. Come back to Sports: the league you watch most is first without "
        "touching the order button.",
    ),
)
