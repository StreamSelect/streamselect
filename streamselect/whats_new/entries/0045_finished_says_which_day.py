from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=45,
    version="1.0.4",
    date="2026-11-14",
    title="Sports: finished games say which day they were",
    items=(
        "Finished games from an earlier day sit under a heading such as Yesterday · Fri 13 Nov, "
        "even when they are the only finished games. Before, last night's game showed just its "
        "time and read as tonight's.",
        "A finished game from an earlier day now lines up with the games above it.",
    ),
    test_steps=(
        "The day after a game night, open Sports and expand Finished: last night's games are "
        "under Yesterday and the date.",
        "Their titles start at the same place as today's games above.",
    ),
)
