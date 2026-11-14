from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=49,
    version="1.0.4",
    date="2026-11-14",
    title="Sports: games sit under their day heading",
    items=(
        "Games under a day heading inside Finished (such as Yesterday) are indented with "
        "that heading, so it's clear which day they belong to.",
    ),
    test_steps=(
        "The day after a game night, expand Finished in Sports: last night's games sit indented "
        "under Yesterday, in line with the heading.",
    ),
)
