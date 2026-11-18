from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=73,
    version="1.0.7",
    date="2026-11-18",
    title="Sports: a guide's shortened team name no longer makes a second game",
    items=(
        "Some TV guides shorten a team's name by leaving out a word, such as \"Vegas Knights\" "
        "for the Vegas Golden Knights. Sports now recognises the shortened name, so the guide's "
        "channel joins the game instead of appearing as a separate, less certain game.",
        "A channel's own listing that adds a word to a team's name is still treated as a "
        "different team.",
    ),
    test_steps=(
        "After a games refresh on a day with a Vegas Golden Knights game, open Sports and turn "
        "on \"Less certain games\": there is one game for that matchup, not a second one "
        "naming \"Vegas Knights\".",
        "Open that game's channel list: a guide channel whose programme says \"Vegas Knights\" "
        "is among its feeds.",
    ),
)
