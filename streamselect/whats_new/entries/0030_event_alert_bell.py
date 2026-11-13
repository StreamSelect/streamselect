from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=30,
    version="1.0.2",
    date="2026-11-13",
    title="Set an alert on a Sports event with its bell",
    items=(
        "Every event card and every Tonight / Tomorrow row has a bell. Click it to be alerted "
        "for that event; it lights in the accent colour, and events still to come say ALERT ON.",
        "Right-click the bell to be alerted for every event of either team, or whenever those "
        "two meet. Each choice is a check item, so clicking it again turns it off.",
    ),
    test_steps=(
        "In Sports, click the bell on an event under Tomorrow: it lights and the row reads "
        "ALERT ON. Click it again: it goes back to the slashed bell.",
        "Right-click a bell and choose \"Alert me for every <team> event\": every row and card "
        "with that team lights; other events do not. Right-click again: that item is checked; "
        "choose it again to turn it off.",
    ),
)
