from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=125,
    version="1.3.1",
    date="2026-11-27",
    title="More games read from the guide",
    items=(
        "A guide that writes its games with a long dash (\"Hokej na ledu – NHL: Carolina – "
        "Seattle\", \"Košarka – ABA liga: Cluj – Zadar\") now has them read: those channels join "
        "their games.",
        "A listing that states both a date and a time zone (\"Fri 27 Nov 17:55 CET\") now gets "
        "its time; it was skipped before.",
    ),
    test_steps=(
        "Start the app and let the Sports view find today's games.",
        "Open a hockey or ABA game that a Croatian or Czech sports guide carries: its channel "
        "list includes that guide's channel.",
    ),
)
