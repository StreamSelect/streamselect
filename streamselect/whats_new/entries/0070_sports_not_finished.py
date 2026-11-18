from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=70,
    version="1.0.7",
    date="2026-11-17",
    title="Sports: bring back a game that went into extra time",
    items=(
        "A finished game no longer opens a channel list: once a game is over, its channels "
        "have moved on to whatever is on now.",
        "If a game is still going (overtime, a shootout), right-click it under Finished and "
        "choose \"Not finished — still on\". It goes back to On now for another 30 minutes; "
        "say it again if it runs longer, or use Mark as finished when it really ends.",
        "The bell on a finished game still sets team and matchup alerts, so you can catch "
        "the next one.",
    ),
    test_steps=(
        "Open Sports after a game has finished today: under Finished its row is plain text, "
        "and clicking it opens nothing.",
        "Right-click that game and choose \"Not finished — still on\": it moves back to On now "
        "as a card marked likely ending, with its channels.",
        "Right-click a game that finished on an earlier day: no menu appears.",
        "Click the bell on a finished game: it offers alerts for the teams and the matchup.",
    ),
)
