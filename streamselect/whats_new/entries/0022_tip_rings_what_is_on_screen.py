from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=22,
    version="1.0.2",
    date="2026-11-12",
    title="The cast tip now appears next to the cast names",
    items=(
        "The tip about clicking a cast or crew name could appear in the top-left "
        "corner of the window, far from the names it explains, when the names were "
        "scrolled out of view in the details pane. It now waits until a name is on "
        "screen and appears beside it.",
    ),
    test_steps=(
        "Choose Tools ▸ Show tips again, click a film in Search and dismiss the like / "
        "not interested / dislike tip.",
        "Click another film whose cast names are below the visible part of the details "
        "pane: no tip appears in the corner of the window.",
        "Click a film whose cast names are visible without scrolling: a tip rings a cast "
        "name and its card sits beside that name.",
    ),
)
