from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=88,
    version="1.0.9",
    date="2026-11-18",
    title="Sports: a short tour, and tips the first time you need them",
    items=(
        "The first time Sports shows games, a short tour points out each part: sports and "
        "their leagues, hiding a league, a game on now, alerts, and how games are listed, "
        "including what \"Less certain games\" adds.",
        "Tips then come once each, the first time they apply: when a game's channel list "
        "opens, when finished games are shown, when a finished game can be put back as "
        "still on, when you hide a league, and when you change a game's length in Settings.",
        "Tools ▸ Show tips again shows the tour and the tips again.",
    ),
    test_steps=(
        "Tools ▸ Show tips again, then open Sports with games listed: the tour starts by "
        "itself, ringing the sport header first, then the league chips, a league, a game on "
        "now, its bell and the toolbar. The last stop explains Less certain games.",
        "Click a game: its channel list opens and a tip explains the channels.",
        "Open a league's Finished list: a tip explains the finished game's bell.",
        "Click a league chip to hide it: a tip says it is hidden from this list only.",
        "In Settings ▸ Sports, pick Hockey and change Usual length: a tip says your value "
        "is kept. Changing another setting shows no tip.",
    ),
)
