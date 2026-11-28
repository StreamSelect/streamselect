from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=131,
    version="1.4.1",
    date="2026-11-28",
    title="Discover opens faster, and a row's name collapses it",
    items=(
        "Discover lays out the whole page at once and then fills the open rows with posters "
        "one by one. Recommended for You, the slowest to work out, fills last, so the rows "
        "below it no longer wait for it.",
        "Clicking a row's name now collapses an open row as well as opening a collapsed one, "
        "on every row (it used to only open).",
    ),
    test_steps=(
        "Open Discover: within about a second your pinned row, Your Shelves and the other "
        "open rows are on screen (showing \"Loading…\" until their posters arrive); "
        "Recommended for You fills last.",
        "Click the name of an open row (Watch Queue, Apple TV+, any genre): it collapses to "
        "one line. Click the name again: it opens. Hover the name: the tooltip says Collapse "
        "or Expand.",
    ),
)
