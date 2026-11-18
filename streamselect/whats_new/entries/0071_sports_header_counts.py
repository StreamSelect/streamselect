from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=71,
    version="1.0.7",
    date="2026-11-17",
    title="Sports: counts that stand out, and the live mark",
    items=(
        "The counts on the Sports headings (On now, each day, Finished) sit in a small "
        "outlined chip in bold, like the chips in the sidebar, so the number stands out "
        "from its label.",
        "A sport's heading shows a chip for each league that has games listed. A league "
        "with games on now shows the live mark and how many in its chip, \"NHL (•) 2\", "
        "instead of the words \"3 live\"; a league with nothing listed has no chip.",
    ),
    test_steps=(
        "Open Sports: On now, each day and Finished show their count in an outlined chip; "
        "clicking the chip collapses the list like the rest of the heading.",
        "With a game on, the sport's heading shows an outlined league chip with the live mark "
        "and a bold number, \"NHL (•) 2\"; hovering it says how many games are on now. "
        "With nothing on, the chip shows the league's name alone.",
    ),
)
