from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=11,
    version="1.0.1",
    date="2026-11-11",
    title="\"|4K|\" and \"|8K|\" at the start of a name count as quality",
    items=(
        "Channels named like \"|4K| BORA BORA\" kept \"|4K|\" in their title, and channels "
        "named like \"|8K| SKY SPORTS 2\" (written with a small capital K) had no quality at "
        "all. The marker now leaves the title and is recorded as 4K or 8K.",
    ),
    test_steps=(
        "Wait for the channel update to finish in the migration progress area after launch.",
        "Open the Quality filter and choose 4K / UHD: a channel such as \"BORA BORA\" is "
        "listed without \"|4K|\" in its name.",
        "Search for SKY SPORTS 2 in the UHD channel folder: it shows 8K quality.",
    ),
)
