from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=77,
    version="1.0.7",
    date="2026-11-18",
    title="Sports: the \"Earliest first\" button is gone",
    items=(
        "The \"Earliest first / Latest first\" button only reordered the cards of games on "
        "now, so it looked as if it did nothing. It has been removed: games on now run "
        "earliest first, days run soonest first, and finished games show the most recent first.",
    ),
    test_steps=(
        "Open Sports: the toolbar shows \"By sport\" and \"Less certain games\", with no "
        "\"Earliest first\" button.",
        "With several games on now, their cards run from the earliest start to the latest.",
    ),
)
