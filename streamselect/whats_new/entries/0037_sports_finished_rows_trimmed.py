from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=37,
    version="1.0.2",
    date="2026-11-13",
    title="Finished games drop what no longer helps",
    items=(
        "A finished game from an earlier day no longer opens a list of channels: those channels "
        "have moved on to other things. Games that finished today still open theirs, in case "
        "one ran late.",
        "A finished game's bell now offers only alerts for its teams (every event of either "
        "team, or whenever the two meet), since an alert for a game that is over has no "
        "point. Clicking it opens those choices.",
    ),
    test_steps=(
        "Open Sports and open Finished. A game from today opens its channel list when clicked; "
        "a game from an earlier day is plain text and does nothing when clicked.",
        "Click the bell on a finished game: a menu offers every event of either team and "
        "whenever the two meet, with no \"this event\" choice.",
    ),
)
