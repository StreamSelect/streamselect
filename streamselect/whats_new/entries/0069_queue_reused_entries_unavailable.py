from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=69,
    version="1.0.6",
    date="2026-11-17",
    title="Watch Queue: an item whose source now shows something else can't play the wrong thing",
    items=(
        "When a source reuses a queued item's number for a different title, the Watch Queue now "
        "shows the item as unavailable instead of playing the stranger, and \"Clear "
        "Unavailable\" removes it.",
        "\"Replace unavailable items…\" lists these too, matched by the title you queued, under "
        "\"Check these first\".",
    ),
    test_steps=(
        "With a queued item whose source now lists a different title under its number (the log "
        "says \"STREAM-ID REUSE: watch queue entry …\"), look at the Watch Queue: it is in the "
        "Unavailable group with the title you queued, and double-clicking it searches for that "
        "title instead of playing.",
        "Open the ⋯ menu's \"Replace unavailable items…\": the item is listed with \"its source "
        "now uses this for another channel\", matched by name if a copy exists, otherwise under "
        "Nothing to replace them.",
    ),
)
