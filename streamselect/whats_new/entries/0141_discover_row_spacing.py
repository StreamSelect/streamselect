from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=141,
    version="1.5.0",
    date="2026-11-28",
    title="Tighter open rows in Discover",
    items=(
        "Less empty space between an open row's posters and its slim scroll bar.",
        "The posters sit straight on the row's card, without a darker box behind them.",
    ),
    test_steps=(
        "Discover: under an open row's titles there is only a small gap before the slim "
        "scroll bar, and the area behind the posters is the same shade as the card.",
    ),
)
