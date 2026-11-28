from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=141,
    version="1.5.0",
    date="2026-11-28",
    title="Tighter open rows in Discover",
    items=(
        "Less empty space between an open row's posters and its slim scroll bar, which is easier to grab: its grab area is taller than the line it draws, the line thickens under the pointer, and the cursor becomes a hand.",
        "The posters sit straight on the row's card, without a darker box behind them.",
    ),
    test_steps=(
        "Discover: under an open row's titles there is only a small gap before the slim "
        "scroll bar, and the area behind the posters is the same shade as the card.",
        "Point at the scroll bar: it thickens and the cursor turns into a hand; drag it to "
        "scroll the row.",
    ),
)
