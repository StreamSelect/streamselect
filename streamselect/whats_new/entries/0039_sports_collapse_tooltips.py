from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=39,
    version="1.0.3",
    date="2026-11-13",
    title="Sports headers say which list they collapse",
    items=(
        "Hovering a Sports section header now names the list it collapses or expands, such as "
        "\"Collapse Tomorrow's games list\", instead of \"Fold these games\".",
        "Tooltips that said \"fold\" now say \"collapse\", like the rest of the app.",
    ),
    test_steps=(
        "Open Sports and hover the Tomorrow header: \"Collapse Tomorrow's games list\". Click "
        "it, hover again: \"Expand Tomorrow's games list\".",
        "Hover On now: \"Collapse the list of games on now\". Hover Finished: \"Collapse the "
        "finished games list\" (or Expand while it is collapsed).",
        "Hover the Hockey header: \"Collapse every Hockey list\".",
        "Open a game's channel list that has hidden channels and show them: the button's "
        "tooltip reads \"Collapse the hidden channels\".",
    ),
)
