from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=54,
    version="1.0.5",
    date="2026-11-16",
    title="Much less CPU while StreamSelect sits open",
    items=(
        "The guide no longer refreshes On Now once a minute while you're on another of "
        "its tabs, such as Watchlist. That refresh used about half a CPU core for several "
        "seconds each time. On Now refreshes when you switch to it.",
        "The record markers in On Now and Browse no longer redraw every row every two "
        "seconds. Only a list on screen is checked, and only rows whose recording state "
        "changed are redrawn. This was a steady load and caused short freezes.",
        "While StreamSelect is hidden in the tray, the screen it was showing stops "
        "refreshing, and picks up again when you bring the window back.",
    ),
    test_steps=(
        "Open the guide on its Watchlist tab and leave it for two minutes: in a system "
        "monitor, StreamSelect's CPU stays low, with no burst each minute.",
        "Switch to On Now: it loads fresh, and the record markers are right.",
        "Schedule a recording of something on now in On Now: its row's marker turns red "
        "within a couple of seconds; cancel it and the marker goes back.",
        "Close the window to the tray with the guide open, wait a minute, then click the "
        "tray icon: the window comes back on the guide, which refreshes.",
    ),
)
