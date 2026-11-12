from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=16,
    version="1.0.1",
    date="2026-11-12",
    title="Switching from Gruvbox to Gruvbox Light keeps the sidebar light",
    items=(
        "Going straight from Gruvbox to Gruvbox Light left the sidebar's sections "
        "dark grey with text that was hard to read. They now switch to the light "
        "colours like the rest of the window.",
    ),
    test_steps=(
        "Choose Style ▸ Theme ▸ Gruvbox, then Style ▸ Theme ▸ Gruvbox Light: the "
        "sidebar sections (Watch Alerts, Recommended, Watch Queue, History) turn "
        "light beige with dark, readable text.",
        "Switch back to Gruvbox: the sections turn dark again.",
    ),
)
