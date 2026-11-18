from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=62,
    version="1.0.6",
    date="2026-11-17",
    title="Watch Queue: replace items on expired sources with a copy that plays",
    items=(
        "The Watch Queue's ⋯ menu has \"Replace unavailable items…\". It lists every queued "
        "item on an expired source (or, if you choose, a switched-off or removed one) beside "
        "the same title on one of your active sources, so you can see exactly what will change.",
        "Matches you can trust come ticked: the same title, in the same language. Anything less "
        "certain, a copy only in another language or a match on the name alone, waits under "
        "\"Check these first\" with the reason beside it. Items with no copy anywhere stay in "
        "your queue as they are.",
        "Replace keeps the window open, so you can do the sure ones first and then go through "
        "the rest. A swapped item keeps its place in the queue, its watch history moves with "
        "it, and every Replace can be undone.",
    ),
    test_steps=(
        "With a source that has expired, open the Watch Queue's ⋯ menu and choose \"Replace "
        "unavailable items…\": each row reads queued copy → copy on an active source, in groups "
        "Ready to replace (ticked), Check these first (unticked, with a note) and Nothing to "
        "replace them (greyed).",
        "Untick one row in Ready to replace and press Replace: the window stays open, the "
        "replaced rows are gone and Check these first is now at the top; the unticked row is "
        "still there.",
        "In the Watch Queue, a replaced item is in the same place and plays from the active "
        "source; one you had partly watched resumes where you left it.",
        "Press Undo on the \"Watch Queue updated\" message: the items point at the expired "
        "source again and reappear in the window.",
    ),
)
