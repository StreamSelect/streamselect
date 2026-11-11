from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=10,
    version="1.0.1",
    date="2026-11-11",
    title="Titles marked \"4K-DS\" and \"4K-AP\" show cleanly",
    items=(
        "Films named like \"|4K-DS| Deadpool 4K\" showed the marker in their title. The "
        "marker is now removed, and DS counts as Disney+ and AP as Amazon Prime, with 4K "
        "recorded as the picture quality.",
    ),
    test_steps=(
        "Wait for the channel update to finish in the migration progress area after launch.",
        "Search for Deadpool: the 4K version's title shows \"Deadpool\", without \"|4K-DS|\", "
        "and its details show Disney+ and 4K.",
    ),
)
