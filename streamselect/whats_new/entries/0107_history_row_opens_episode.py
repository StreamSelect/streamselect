from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=107,
    version="1.2.0",
    date="2026-11-23",
    title="Selecting a show in History opens its episode",
    items=(
        "History: selecting a show's row (the one with an episode code like S04E01) opens "
        "that episode in the details pane, with its Resume point, instead of the series. "
        "Films and live channels open as before.",
    ),
    test_steps=(
        "In History, click a show's row: the details pane shows the episode named on the "
        "row (its title, season and episode, Start over / Resume), over the series.",
        "Click a film in History: the film's details show as before.",
    ),
)
