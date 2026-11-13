from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=23,
    version="1.0.2",
    date="2026-11-12",
    title="Sports: the games on right now, without knowing who's playing",
    items=(
        "A new Sports view in the top bar shows every NHL game on right now as a card, "
        "with how long it has been going, then the games later today and tomorrow, and "
        "the ones that have finished.",
        "A game is found by matching its listings across your sources' collections and "
        "the programme guide, so one card stands for every channel showing it. Only games "
        "that two or more collections agree on are shown.",
        "Click a game to list every channel showing it, and play any of them; "
        "double-click a game, or its play button, to play the best one. A channel found "
        "only through the programme guide is marked EPG.",
        "Recommended has moved from the top bar to a gear button on the Recommended list "
        "in the sidebar.",
    ),
    test_steps=(
        "During an NHL game, click Sports in the top bar: the game is a card marked LIVE "
        "with how long it has been on, and its channel count.",
        "Click the card: a Watch on list appears below the cards with every channel "
        "showing the game; click one and it plays.",
        "Double-click a card: its best channel plays.",
        "Outside game hours, open Sports: the next game is named with its day and time, "
        "and the later games are listed under Tonight / Tomorrow headings.",
        "In the sidebar, click the gear on the Recommended header: the Recommended view "
        "opens and no top-bar view is lit. The top bar shows Search, EPG, Sports, "
        "Discover, Recipe.",
        "Choose Tools ▸ Take the tour: the top bar card mentions Sports, and the Your lists "
        "card mentions the gear on Recommended.",
    ),
)
