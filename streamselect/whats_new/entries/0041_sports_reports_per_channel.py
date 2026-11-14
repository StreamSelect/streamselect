from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=41,
    version="1.0.3",
    date="2026-11-13",
    title="Sports reports count for one channel, not its whole package",
    items=(
        "No picture and Not this game now apply to the channel you reported. Before, they "
        "applied to every channel in the same package, so one dead channel pushed the "
        "working ones down in every game too.",
        "Watching that channel for a minute or more takes one of its reports back, as before; "
        "watching a different channel in the same package no longer does.",
        "Hover the channel line on a game's card to see the channel's own name, so two games "
        "listed in the same package can be told apart.",
    ),
    test_steps=(
        "Open Sports while two games are on that both list a channel from the same package. "
        "Report No picture on one card: only that card is flagged; the other is unchanged.",
        "Open a game with several channels from one package (+N) and report one row: only that "
        "row is flagged and moved last; the other rows from the same package stay where they were.",
        "Report Not this game on a one-channel card: it shows the flag but does not dim.",
        "Hover a card's channel line: the tooltip ends with the channel's full name and its package.",
    ),
)
