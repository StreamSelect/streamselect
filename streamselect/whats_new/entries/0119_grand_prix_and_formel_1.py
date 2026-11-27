from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=119,
    version="1.3.0",
    date="2026-11-27",
    title="Grand Prix weekends and skating in more languages",
    items=(
        "Formula 1 listings written \"Formel 1\" (Danish, German, Swedish) are now Sports "
        "and show Formula 1.",
        "MotoGP's Tissot Sprint, Moto2 and Moto3 show as MotoGP.",
        "A listing that only says \"Grand Prix\" is shown as racing, marked as a guess: "
        "skating, darts and snooker have Grand Prix events too, so any other sport word in "
        "the name wins, and \"Grand Prix\" alone never makes a channel a sports channel.",
        "Figure skating is recognised in German, Spanish and French (Eiskunstlauf, "
        "Patinaje artístico, Patinage artistique), and the ISU Grand Prix is its league.",
    ),
    test_steps=(
        "Start the app: \"Re-sorting sports and events\" runs once in the background and "
        "finishes.",
        "Search \"Tissot Sprint\": the row shows Racing and MotoGP.",
        "Search \"Formel 1\": the rows show Racing and Formula 1.",
        "Search \"Eiskunstlauf\": the rows show Figure skating.",
        "Search \"Grand Prix Radio\": the station is not a sports channel.",
    ),
)
