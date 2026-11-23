from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=104,
    version="1.2.0",
    date="2026-11-23",
    title="An upcoming game's channels line up under the game",
    items=(
        "Sports: the channel list under a later game now starts where the game's title does, "
        "so it reads as that game's channels rather than more games at that time.",
        "Every channel row keeps a small column on the left for the report flag, so a flagged "
        "channel's name no longer sits further right than the others.",
    ),
    test_steps=(
        "In Sports, click a later game, including one of several games at the same time: its "
        "channels appear indented under the game's title, not under the time.",
        "Report one of those channels \"Nothing showing\": its flag appears in the left column "
        "and its name stays lined up with the other channel names.",
        "Expand a live card's channels (+N): the names line up the same way, flagged or not.",
    ),
)
