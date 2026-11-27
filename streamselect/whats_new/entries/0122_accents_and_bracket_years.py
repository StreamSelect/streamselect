from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=122,
    version="1.3.1",
    date="2026-11-27",
    title="Accented titles and bracketed years read correctly",
    items=(
        "A title is the same title however its accents were typed. Some sources send a letter "
        "like \"ö\" as two characters; those episodes (\"Gönül Dağı 215. Bölüm\") now collapse "
        "into their show like the others, and such a film groups with its other listings.",
        "A year in square brackets at the end of a name is the year: \"MOTO GP Assen 500cc "
        "[1980]\" and \"[1984]\" are two titles, each showing its year.",
    ),
    test_steps=(
        "Start the app and let the one-time title re-read finish (Tools ▸ Migration Center "
        "shows it).",
        "Search \"Assen 500cc\": the 1980 and 1984 races are separate results, each with its year.",
        "Search \"Gönül Dağı\": one card for the show, not one per \"Bölüm\" episode.",
    ),
)
