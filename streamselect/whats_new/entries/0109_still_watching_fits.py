from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=109,
    version="1.2.1",
    date="2026-11-23",
    title="The \"Still watching?\" question is no longer cut off",
    items=(
        "The dialog that asks whether you watched the episodes a queue played through is "
        "wider, so its question is shown in full.",
    ),
    test_steps=(
        "Queue several episodes, let the queue move past at least one, and close the player: "
        "\"Still watching?\" shows \"The queue auto-advanced through N more episodes.\" and "
        "\"Did you watch them?\" in full, with the tick, the link and Yes / No below.",
    ),
)
