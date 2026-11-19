from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=80,
    version="1.0.7",
    date="2026-11-18",
    title="Sports: clicking WATCHING shows the channels; long team names keep cards even",
    items=(
        "On the card of the game you're watching, clicking the WATCHING line (or "
        "double-clicking the card) now opens or closes its list of channels instead of "
        "restarting the stream.",
        "A card with a long team name, such as \"Wilkes Barre Scranton Penguins\", is no longer "
        "taller than the cards beside it.",
    ),
    test_steps=(
        "Play a game from its Sports card, then click the card's WATCHING line: the list of "
        "channels opens and the stream keeps playing without restarting. Click it again: the "
        "list closes.",
        "With a game on now whose team has a long name, look at the On now cards: every card "
        "is the same height, and the country chip on the play line is its normal size.",
    ),
)
