from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=9,
    version="1.0.1",
    date="2026-11-11",
    title="\"DISNEY 4K\" folders count as Disney+",
    items=(
        "Titles in a source folder named \"DISNEY 4K\" (Pixar, Disney, 20th Century and Hulu "
        "films) now count under Disney+, with 4K recorded as their picture quality.",
    ),
    test_steps=(
        "Wait for the channel update to finish in the migration progress area after launch.",
        "Choose Disney+ in the Platform filter: titles such as Cars 3 or Deadpool from a "
        "\"DISNEY 4K\" folder are included and show 4K quality.",
    ),
)
