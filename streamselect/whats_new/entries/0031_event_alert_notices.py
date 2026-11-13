from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=31,
    version="1.0.2",
    date="2026-11-13",
    title="Event alerts tell you before an event starts, and when it starts",
    items=(
        "An event you set an alert on (the bell in Sports) now shows a notification 15 minutes "
        "before it starts and another when it starts, each with a Play button that plays the "
        "channel the event's card would play.",
        "Settings ▸ Content ▸ Live catalog ▸ Event alerts sets how many minutes before; 0 "
        "means only when it starts.",
    ),
    test_steps=(
        "Set Settings ▸ Content ▸ Event alerts to 30 minutes. In Sports, click the bell on an "
        "event starting within 30 minutes: within half a minute a notification says \"Starting "
        "in N minutes\" with the event and its channel; click Play: that channel plays.",
        "Leave the app open until the event starts: a second notification says \"Starting now\".",
    ),
)
