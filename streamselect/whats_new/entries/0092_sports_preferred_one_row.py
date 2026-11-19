from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=92,
    version="1.1.0",
    date="2026-11-19",
    title="Sports: PREFERRED shows on the channel that will play",
    items=(
        "A preferred channel is remembered for its whole package, because event channels "
        "change between refreshes. PREFERRED now shows on one row only: the channel the "
        "game will actually play from that package, not on every channel in it.",
        "A channel you reported never shows PREFERRED and is never the one a preference "
        "plays.",
    ),
    test_steps=(
        "Open a game whose channel list has several channels from one package (e.g. several "
        "Sportsnet channels) and click PREFERRED on one: PREFERRED shows on that package's "
        "first channel only, the one the card plays.",
        "Report that channel as \"Nothing showing\": PREFERRED moves to the package's next "
        "channel, and the reported one goes to the bottom without it.",
    ),
)
