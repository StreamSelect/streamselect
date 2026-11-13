from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=35,
    version="1.0.2",
    date="2026-11-13",
    title="Sports headers fold from anywhere you click on them",
    items=(
        "A click anywhere on a sport's header (its arrow, icon, name or the space beside them) "
        "folds or opens that sport. Before, only the name worked.",
        "The same for the sections inside a sport: the arrow, the label and the empty space "
        "all fold or open it.",
        "On now can be folded too, like the other sections.",
    ),
    test_steps=(
        "Open Sports and click the empty space at the right of the Hockey header: the hockey "
        "segment folds. Click its arrow: it opens.",
        "Click the arrow beside On now: the cards fold away and On now's header stays. Click "
        "the empty space on that header: the cards come back.",
    ),
)
