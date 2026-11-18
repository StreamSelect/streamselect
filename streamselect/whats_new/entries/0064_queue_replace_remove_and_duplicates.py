from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=64,
    version="1.0.6",
    date="2026-11-17",
    title="Replace unavailable items: remove what you no longer want, and spot duplicates",
    items=(
        "Each row in \"Replace unavailable items…\" has a trash button at the far right. It "
        "strikes the item through: it is not replaced but taken out of your queue when you "
        "press the button at the bottom. Click it again to keep the item. A group's own trash "
        "button does the same for every item in it.",
        "Items whose title is already in your queue from an active source now have their own "
        "group, \"Already in your queue\", so a duplicate is easy to clear out instead of being "
        "swapped into a second copy.",
        "Items on a source you deleted say \"a removed source\" instead of a code.",
    ),
    test_steps=(
        "Open \"Replace unavailable items…\" from the Watch Queue's ⋯ menu and click a row's "
        "trash button: the row is struck through, its note says it will be removed, and the "
        "button at the bottom reads \"Remove 1\" (or \"Replace N · Remove 1\").",
        "Click the trash button again: the row is back to normal and can be ticked.",
        "Queue a title from an active source that is also queued from an expired one: the "
        "expired copy is under \"Already in your queue\", with the active source named.",
        "Strike an item, press the button, then Undo on the \"Watch Queue updated\" message: "
        "the item is back in the queue in its old place.",
    ),
)
