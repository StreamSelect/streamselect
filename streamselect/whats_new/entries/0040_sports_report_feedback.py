from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=40,
    version="1.0.3",
    date="2026-11-13",
    title="A reported Sports channel shows that you reported it",
    items=(
        "After you report a channel with No picture or Not this game, the menu shows a tick "
        "beside your choice. Choose it again to take the report back.",
        "When a game has no unreported channel left to play, its card dims and shows a flag "
        "beside the channel. Hover the flag to see what you reported.",
    ),
    test_steps=(
        "Open Sports while a game with one channel is on. Right-click its card and choose No "
        "picture: the card dims and a flag appears beside the channel name.",
        "Right-click the card again: No picture is ticked. Choose it: the tick, the flag and "
        "the dimming all go.",
        "On a game with several channels, report its channel from the card: the card stays "
        "bright and switches to the next channel; the reported one is last in its +N list "
        "with a flag, and its row menu shows No picture ticked.",
    ),
)
