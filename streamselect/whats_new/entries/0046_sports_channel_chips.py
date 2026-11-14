from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=46,
    version="1.0.4",
    date="2026-11-14",
    title="Sports: channel quality chips match the rest of the app",
    items=(
        "In a game's channel list, the quality chip (HD, 4K, RAW…) is now the same outlined "
        "chip the channel list and details pane use, instead of a solid colour block.",
        "The EPG and quality chips keep their place on every row, so they line up down the "
        "list even when a channel has neither.",
    ),
    test_steps=(
        "Open a live game in Sports: quality chips are outlined, with the tier's colour in the "
        "text, like the main channel list.",
        "In a game whose channels mix EPG and quality chips, the EPG chips form one column and "
        "the quality chips another.",
    ),
)
