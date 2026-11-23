from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=107,
    version="1.2.0",
    date="2026-11-23",
    title="Click a show's episode code in History to open that episode",
    items=(
        "History: on a show's row, the episode code (like S04E01) is now a button. Click it "
        "and the details pane opens that episode, with its Resume point. Click the show's name "
        "or anywhere else on the row and you get the series, as before.",
    ),
    test_steps=(
        "In History, hover a show's S04E01 chip: the pointer becomes a hand and the tooltip "
        "says \"Show S04E01 in the details pane\". Click it: the pane shows that episode "
        "(title, season and episode, Start over / Resume) and the row is selected.",
        "Click the show's name on the same row: the pane shows the series.",
        "A film's year chip is not clickable; clicking the film's row shows the film.",
    ),
)
