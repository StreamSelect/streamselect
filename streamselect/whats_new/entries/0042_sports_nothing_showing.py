from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=42,
    version="1.0.3",
    date="2026-11-13",
    title="\"Nothing showing\" replaces \"No picture\"",
    items=(
        "The Sports report for a channel that shows black or nothing is now called Nothing "
        "showing. A dead stream and a channel with no game on it look the same, and \"No "
        "picture\" sounded like the stream was broken.",
    ),
    test_steps=(
        "Right-click a game that is on now in Sports: the reports read Nothing showing and Not "
        "this game.",
        "Choose Nothing showing and hover the flag beside the channel: it says nothing showing.",
    ),
)
