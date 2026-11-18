from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=74,
    version="1.0.7",
    date="2026-11-18",
    title="Sports: a misspelt or shortened team name joins the right game",
    items=(
        "A listing that swaps two letters in a team's name, such as \"Florida Phanters\", "
        "now counts as that team, and so does a guide's initial, such as \"F. Panthers\". Their "
        "channels join the game instead of making a second copy of it.",
        "With those listings joined, a game can become confident sooner, and a guide's later "
        "showings of it are recognised as replays.",
    ),
    test_steps=(
        "After a games refresh on a day a guide lists a game under a misspelt or shortened team "
        "name, open Sports with \"Less certain games\" on: the matchup appears once, not once "
        "per spelling.",
        "Open that game's channel list: the guide channel with the misspelt name is among its "
        "feeds.",
    ),
)
