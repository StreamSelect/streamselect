from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=132,
    version="1.5.0",
    date="2026-11-28",
    title="Discover shows \"Loading…\" while a row fills",
    items=(
        "A row waiting for its posters now says \"Loading…\" (and an error, if it couldn't "
        "load). The text was there but squeezed to nothing, so a slow row such as Recommended "
        "for You looked like empty space.",
    ),
    test_steps=(
        "Open Discover: Recommended for You shows \"Loading…\" until its posters appear.",
        "Expand a collapsed genre: \"Loading…\" shows in the row until its posters arrive.",
    ),
)
