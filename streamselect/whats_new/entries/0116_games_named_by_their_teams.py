from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=116,
    version="1.3.0",
    date="2026-11-27",
    title="Games are recognised by their teams",
    items=(
        "A game listing that names two teams but no sport or league (\"TORONTO MAPLE LEAFS "
        "VS. BOSTON BRUINS\") now shows its sport and league when both teams are known "
        "teams of one league, learned from the games the Sports view found.",
        "A matchup that fits two leagues (\"Toronto @ Boston\" could be hockey or basketball) "
        "stays \"Unknown\".",
    ),
    test_steps=(
        "Start the app and wait for the Sports view to find today's games.",
        "Channels: search \"MAPLE LEAFS VS\" (or another NHL matchup listed without "
        "\"NHL\"): the rows show Hockey and NHL instead of \"Unknown\".",
        "Search \"Toronto @ Boston\": a row with only city names still shows \"Unknown\".",
    ),
)
