from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=14,
    version="1.0.1",
    date="2026-11-12",
    title="The tour explains which rows are live",
    items=(
        "The tour has a new second stop on the channel list. It shows the mark at "
        "the start of each row: a live channel joins the broadcast already in "
        "progress, while a movie or a series episode starts from the beginning.",
    ),
    test_steps=(
        "Choose Tools ▸ Take the tour and press Next once: the channel list is "
        "ringed and the card shows the live, movie and series marks, each with a "
        "line saying what playing it does.",
        "Compare the card with the list: the live mark has the same colour as on "
        "live rows.",
        "Press Next: the marks are gone from the card for the top bar stop.",
    ),
)
