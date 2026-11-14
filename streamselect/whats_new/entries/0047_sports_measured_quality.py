from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=47,
    version="1.0.4",
    date="2026-11-14",
    title="Sports: a channel you've played shows the quality it really had",
    items=(
        "Once a game's channel has played, its quality chip shows what the stream measured "
        "(for example FHD for 1080p) with the measured mark, instead of what the channel's name "
        "claims. The same rule the details pane's versions use.",
    ),
    test_steps=(
        "Play a channel from a live game in Sports and let it run a few seconds: its row's "
        "quality chip changes to the measured tier with a check mark, and its tooltip begins "
        "Measured while playing.",
        "Channels you haven't played keep the quality their name states, with no mark.",
    ),
)
