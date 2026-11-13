from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=34,
    version="1.0.2",
    date="2026-11-13",
    title="The several-channels mark in Watch Alerts no longer starts a recording",
    items=(
        "Clicking the mark beside an EPG alert that plays on several channels started a "
        "recording, though recording is not available yet. It now opens the list of channels, "
        "as it was meant to.",
    ),
    test_steps=(
        "In Watch Alerts, find an EPG row with the several-channels mark at its left and click "
        "the mark: the row opens to list its channels, and no \"recording\" notice appears.",
    ),
)
