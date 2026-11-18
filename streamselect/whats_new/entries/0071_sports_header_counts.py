from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=71,
    version="1.0.7",
    date="2026-11-17",
    title="Sports: counts that stand out, and the live mark",
    items=(
        "The counts on the Sports headings (On now, each day, Finished) sit in the same small "
        "outlined chip the sidebar uses, so the number stands out from its label.",
        "A sport's heading shows how many games are on with the live mark and the number, "
        "instead of the words \"3 live\".",
    ),
    test_steps=(
        "Open Sports: On now, each day and Finished show their count in an outlined chip; "
        "clicking the chip collapses the list like the rest of the heading.",
        "With a game on, the sport's heading reads its leagues then the live mark and a "
        "number, in the same quiet grey; hovering it says how many games are on now.",
    ),
)
