from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=133,
    version="1.5.0",
    date="2026-11-28",
    title="Recommended for You appears at once; pinned rows stay pinned when collapsed",
    items=(
        "Discover remembers your last recommendations and shows them as soon as it opens. "
        "They are worked out again only when something they depend on changes (a like or "
        "dislike, a favourite, something you played, new titles, your exclusions or sources); "
        "meanwhile the remembered ones stay on screen and the new ones replace them.",
        "Collapsing a pinned row keeps it pinned, folded in place at the top. Before, it lost "
        "its pin and dropped down to its section.",
    ),
    test_steps=(
        "Open Discover twice in a row (switch away and back, or restart): the second time, "
        "Recommended for You has its posters straight away.",
        "Like or dislike a title, then open Discover: the old recommendations show at once and "
        "are replaced a few seconds later.",
        "Collapse a pinned row: it folds in place and stays at the top. Restart: still pinned "
        "and collapsed. Expand it again: opens in place.",
    ),
)
