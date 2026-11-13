from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=36,
    version="1.0.2",
    date="2026-11-13",
    title="Finished games are grouped by day when they span more than one",
    items=(
        "When Sports' Finished section holds games from different days, each day gets its own "
        "heading inside it (\"Today\", \"Yesterday\", then the date), most recent first, and "
        "each day folds on its own. Games all from one day stay in a single list.",
    ),
    test_steps=(
        "Open Sports late on a game day, or the morning after, and open Finished. If its games "
        "come from two days, each day has its own indented heading, the most recent first; "
        "click one to fold that day only.",
    ),
)
