from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=82,
    version="1.0.8",
    date="2026-11-18",
    title="Sports: four more hockey leagues, and leagues with nothing left go last",
    items=(
        "Sports now also looks for games in Liiga (Finland), the Champions Hockey League, "
        "Hockey Ettan (Sweden) and Metal Ligaen (Denmark). They are on trial while their "
        "results are checked.",
        "A league whose games are all finished now sits below the leagues with games on now "
        "or still to come, whichever order you picked. Sports follow the same rule.",
        "A team written as one word in one listing and two in another (\"BoroVetlanda\" / "
        "\"Boro/Vetlanda\") is now recognised as the same team.",
    ),
    test_steps=(
        "On an evening with European hockey, open Sports: Hockey shows a heading for each "
        "league with games, such as Liiga or Hockey Ettan, beside NHL.",
        "Once one league's games for the day are all over, it moves below the leagues that "
        "still have games on or to come.",
    ),
)
