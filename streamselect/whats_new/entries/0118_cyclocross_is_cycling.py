from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=118,
    version="1.3.0",
    date="2026-11-27",
    title="Cyclocross and BMX are cycling",
    items=(
        "UCI Cyclocross World Cup races and FloSports cycling (flobikes) listings, BMX "
        "included, now show the sport Cycling, with the UCI as the league where it's named.",
    ),
    test_steps=(
        "Start the app: \"Re-sorting sports and events\" runs once in the background and "
        "finishes.",
        "Search \"Cyclocross\": the race rows show Cycling and UCI, not \"Unknown\".",
        "Tools ▸ Library Breakdown ▸ Nothing identified: no UCI Cyclocross row is listed "
        "under \"Not a game\".",
    ),
)
