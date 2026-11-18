from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=63,
    version="1.0.6",
    date="2026-11-17",
    title="Watch Queue: \"Remove from Watch Later\" is easier to find",
    items=(
        "In the Watch Queue's right-click menu, \"Remove from Watch Later\" now sits on its own, "
        "just under the play options, with a line above and below it.",
    ),
    test_steps=(
        "Right-click an item in the Watch Queue: \"Remove from Watch Later\" comes right after "
        "the play options, set apart by a line above and below; choosing it removes the item.",
    ),
)
