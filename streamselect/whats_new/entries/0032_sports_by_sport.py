from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=32,
    version="1.0.2",
    date="2026-11-13",
    title="Sports groups events by sport",
    items=(
        "Sports now has a header for each sport, starting with Hockey, showing its leagues and how "
        "many events are live. Click it to fold that sport away; other sports will get their "
        "own headers as they are added.",
        "Sort order and \"Less certain games\" moved to the top of the view, since they apply to "
        "every sport.",
    ),
    test_steps=(
        "Open Sports: a Hockey header with a puck shows \"NHL · N live\" above On now. Click "
        "Hockey: the whole hockey segment folds; click again: it opens.",
    ),
)
