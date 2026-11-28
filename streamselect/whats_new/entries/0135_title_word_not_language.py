from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=135,
    version="1.4.1",
    date="2026-11-28",
    title="Film titles no longer lose their first word to a fake language",
    items=(
        "A name like \"Avatar - Fuoco e cenere\" was read as language \"AVATAR\" and title "
        "\"Fuoco e cenere\". A word before the dash is now kept in the title unless it is a "
        "real language, region, service or quality code (\"En - Pretty Woman\" still reads "
        "as English). About 56 films were affected on a large library.",
        "A provider's catalogue number at the end of a name (\"[ID37849]\") and a quality "
        "written \"[m2160p]\" no longer stay in the title.",
        "The first launch after updating re-reads existing titles (Migration Center).",
    ),
    test_steps=(
        "Launch once and let the title re-read finish (Tools ▸ Migration Center).",
        "Find \"Avatar - Fuoco e cenere\": the title reads \"Avatar - Fuoco e cenere\" with "
        "4K and 2025, and no AVATAR chip.",
        "Find an \"En - …\" film: it still shows EN as its language.",
    ),
)
