from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=2,
    version="1.0.0",
    date="2026-11-07",
    title="F11 for full screen",
    items=("Press F11 to make the app full screen, and again to return to the window you had.",),
    test_steps=("Press F11: the app fills the screen, with no title bar.",
                "Press F11 again: the window returns to its earlier size. If it was maximized, "
                "it comes back maximized.",
                "Click in the search box and press F11: it still toggles, and no text is typed.",
                "Open Help's keyboard shortcuts list: F11 is listed under Panels.",),
)
