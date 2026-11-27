from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=126,
    version="1.3.1",
    date="2026-11-27",
    title="Other broadcasts on now",
    items=(
        "Some channels are on air with a league's game, or a show about it, without saying "
        "which teams: a \"Matchday\" slot, a guide's \"Live: NHL Hockey\". They now appear under "
        "the league's On now, in their own section of smaller, darker cards that say LIVE and "
        "whether the title came from the GUIDE or the channel's NAME.",
        "A Games | All switch on the right of On now hides them (Games) or shows them (All). "
        "It applies to every league and is remembered.",
        "A programme two leagues match goes to the more specific one: \"NBA G League\" is G League.",
    ),
    test_steps=(
        "Start the app while a league has a game on, and open Sports.",
        "Under that league's On now, \"Other broadcasts on now\" lists any slot or guide "
        "programme naming the league without teams, as half-height cards below the game cards.",
        "Click a card's channel line: it plays that channel. A card with \"+N\" opens its other "
        "channels; clicking one plays it.",
        "Click Games on On now's header: the section goes, in every league. Restart: Games is "
        "still chosen. Click All to bring it back.",
    ),
)
