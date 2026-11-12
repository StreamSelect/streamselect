from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=15,
    version="1.0.1",
    date="2026-11-12",
    title="The tour starts by letting you pick a theme",
    items=(
        "The tour now opens on a card in the middle of the window listing every "
        "theme, each with a small preview in its own colours. Clicking one "
        "switches to it straight away and keeps it. The card points to Style ▸ "
        "Theme in the menu bar, where the theme can be changed later.",
    ),
    test_steps=(
        "Choose Tools ▸ Take the tour: the first card sits in the middle of the "
        "window, lists every theme with the current one highlighted, and rings "
        "Style in the menu bar.",
        "Click Daylight: the whole window switches to Daylight at once and the "
        "Daylight row becomes the highlighted one.",
        "Press Next, then open Style ▸ Theme: Daylight is the ticked entry.",
        "Quit and relaunch: the app opens in Daylight.",
    ),
)
