from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=136,
    version="1.5.0",
    date="2026-11-28",
    title="Scrolling Discover no longer gets caught on a row",
    items=(
        "Scrolling up or down over a row of posters (or its scroll bar) now keeps scrolling "
        "the page. Before, the page stopped and the row slid sideways.",
        "To move a row sideways: swipe sideways on a trackpad, tilt the wheel, or hold Shift "
        "while turning the wheel.",
    ),
    test_steps=(
        "Discover with several open rows: scroll down with the mouse wheel while the pointer "
        "passes over posters and scroll bars: the page keeps scrolling, no row moves.",
        "Hold Shift and turn the wheel over a row: that row moves sideways.",
    ),
)
