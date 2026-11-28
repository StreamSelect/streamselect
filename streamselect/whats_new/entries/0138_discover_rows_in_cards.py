from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=138,
    version="1.5.0",
    date="2026-11-28",
    title="Discover's open rows sit in cards; tiles keep their posters",
    items=(
        "An open row in Discover now sits in a card like the tiles, with a slim scroll bar "
        "inside it instead of a full-width bar underneath.",
        "Tile names are bolder and a size larger, so they stand out from the posters.",
        "Opening or collapsing a row no longer makes the other tiles reload their posters.",
        "When Discover reloads (after a background re-read of your library, or a change of "
        "sources), it returns to where you were instead of jumping to the top.",
    ),
    test_steps=(
        "Open Discover: each open row has a soft card behind it and a slim scroll bar inside "
        "its bottom edge.",
        "Tile names read clearly in bold.",
        "With Discover's Shelves showing tiles with posters, collapse Recently Added: the other "
        "tiles keep their posters (no blanking). Open and collapse a decade: same.",
        "Scroll halfway down Discover, then switch sources off and on (or wait for a background "
        "re-read to finish): Discover reloads and comes back to the same place.",
    ),
)
