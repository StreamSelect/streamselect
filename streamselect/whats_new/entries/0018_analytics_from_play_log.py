from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=18,
    version="1.0.1",
    date="2026-11-12",
    title="A source's viewing numbers no longer reset when you clear History",
    items=(
        "What you watch here in a source's Analytics tab now counts every play the app "
        "has recorded. Before, clearing History wiped its titles, plays and Most played "
        "list, and episodes never counted at all.",
        "Most played now says the date it counts from, counts a series' episodes "
        "together under the series, and shows how long you watched each title. Ties go "
        "to the one you played most recently.",
        "A live channel in Most played keeps the name it had when you watched it, so a "
        "game no longer shows up under whatever that channel is showing today.",
    ),
    test_steps=(
        "Open Sources, choose a source you have watched from, and open its Analytics "
        "tab: the list heading reads \"Most played since\" followed by a date.",
        "A series you watched several episodes of is listed once, with the episodes' "
        "plays added together and the time watched beside them.",
        "Clear History from the History section, then reopen the Analytics tab: the "
        "numbers and the Most played list are unchanged.",
    ),
)
