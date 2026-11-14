from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=48,
    version="1.0.4",
    date="2026-11-14",
    title="Sports: game cards show the matchup, and who's at home",
    items=(
        "A live game's card puts one team on each line, centred, with a small \"vs\" between "
        "them, so a name never breaks across lines and every card is the same height.",
        "When a channel's listing says \"Kraken @ Hurricanes\" or \"Kraken at Hurricanes\", the "
        "game reads \"Seattle Kraken at Carolina Hurricanes\", home team second, on cards and "
        "rows. If listings disagree, it says \"vs\".",
        "The league's own logo, taken from its channels' logos, sits very faintly behind each "
        "card.",
    ),
    test_steps=(
        "Open Sports while games are on: each card shows one team, a small rule-framed vs or "
        "at, then the other team, centred.",
        "A game whose channels say \"@\" reads away at home, on the card and in the later "
        "games list.",
        "Look closely behind a card's teams: the league's logo is just visible. A league none of "
        "whose channels carry its logo shows none.",
    ),
)
