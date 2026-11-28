from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=137,
    version="1.5.0",
    date="2026-11-28",
    title="Collapsed rows in Discover are now poster tiles",
    items=(
        "A collapsed row is a tile showing its four newest titles, its name and how many "
        "titles it holds. Tiles sit side by side and fill the width, as many across as fit, "
        "instead of a long list of names down one side.",
        "Hover a poster on a tile to see its title. Click a tile to open that row right where "
        "the tile was; the next time Discover opens, open rows come first in their section.",
        "Pin and hide appear on a tile when you hover it, as on a row.",
        "A tile loads its posters when it scrolls into view.",
    ),
    test_steps=(
        "Open Discover and unfold Genres: each genre is a tile with posters, a name and a "
        "count (\"17.3k titles\"), several per row, the row filled edge to edge.",
        "Make the window narrower: fewer tiles per row, still filling the width.",
        "Hover a poster on a tile: its title shows. Click the tile: the genre opens as a row "
        "where it was, the other tiles above and below it.",
        "Switch away from Discover and back (or restart): the opened genre now leads Genres.",
        "Hover a tile: pin and hide show in its corner; pin it and it moves to the top.",
    ),
)
