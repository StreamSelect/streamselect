from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=13,
    version="1.0.1",
    date="2026-11-11",
    title="Country and language markers at the end of a name are read",
    items=(
        "Channels named like \"BENFICA TV |PT|\" or \"IMAM HUSSEIN 1 TV |PERSIAN|\" kept the "
        "marker in their title. The country or language is now recorded and the marker "
        "leaves the title. Local feeds keep their place in brackets, as in "
        "\"NBC SPORTS HD (BOSTON)\".",
    ),
    test_steps=(
        "Wait for the channel update to finish in the migration progress area after launch.",
        "Search for BENFICA TV: it is listed as \"BENFICA TV\" without \"|PT|\" and shows "
        "Portugal.",
        "Search for NBC SPORTS: the Boston feed reads \"NBC SPORTS HD (BOSTON)\".",
    ),
)
