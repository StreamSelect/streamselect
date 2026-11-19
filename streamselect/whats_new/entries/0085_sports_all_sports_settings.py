from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=85,
    version="1.0.8",
    date="2026-11-18",
    title="Sports: settings for all sports at once; the NBA gets its banner",
    items=(
        "Settings ▸ Sports opens on All sports: a value set there applies to every sport, "
        "and a sport can still set its own. Game lengths are set per sport; \"Most watched\" "
        "and the clock settings apply to all sports.",
        "A sport's value that comes from All sports says \"from All sports\" beside it.",
        "The NBA has the same banner and frame as hockey's leagues, even as basketball's "
        "only league.",
        "Basketball games are shorter than first estimated: they show as likely ending after "
        "1 h 45 and finished after 2 h 15.",
        "Every league's Finished list starts collapsed.",
    ),
    test_steps=(
        "Open Settings ▸ Sports: All sports is selected, with no game length group, and "
        "\"Most watched\" looks back is listed under What counts as watching.",
        "Set \"Show games up to\" to 24 h ahead, pick Hockey: it shows 24 h ahead with "
        "\"from All sports\" beside it and no Reset. Change it to 12: \"default 36 h ahead\" "
        "and Reset appear.",
        "Pick Basketball: Usual length 1 h 45 min, Longest a game runs 2 h 15 min; "
        "\"Most watched\" is not listed.",
        "Open Sports with NBA games: an NBA banner, centred between two rules, sits over a "
        "frame holding the NBA games, like Hockey's leagues.",
        "An NBA game 1 h 50 after its listed start shows as likely ending.",
    ),
)
