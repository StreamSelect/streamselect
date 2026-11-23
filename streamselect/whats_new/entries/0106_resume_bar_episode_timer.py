from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=106,
    version="1.2.0",
    date="2026-11-23",
    title="See how far in you are, and a live timer for the episode playing",
    items=(
        "The Resume button now has a thin bar along its bottom showing how far into the "
        "episode or film you stopped, so you can tell a resume near the end at a glance.",
        "While the episode shown in the details pane is the one playing, its Play button "
        "shows a live timer that keeps time with the player, as films already did. Resume "
        "steps aside until you stop.",
        "Sports: the measured language now sits left of the report flag, in a column every "
        "game keeps, so channel names start in the same place in every game's list.",
    ),
    test_steps=(
        "Select an episode you stopped partway: under \"Resume M:SS\" a bar fills about as far "
        "as you got. Hover it: the tooltip adds \"N% in\".",
        "Play that episode and keep it selected: the Play button counts up every second in "
        "step with mpv and Resume is hidden. Stop: \"Start over\" and \"Resume\" come back.",
        "Select a different episode while one plays: no timer on it.",
        "In Sports, open a game with a measured language (EN) and one without: the channel "
        "names start at the same place in both; the language chip is left of the flag.",
    ),
)
