from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=114,
    version="1.3.0",
    date="2026-11-27",
    title="Every sports event channel gets a sport",
    items=(
        "Event channels such as \"SKY SPORTS UHD [EVENT]\" no longer go untagged: they "
        "read \"Many sports\", or their sport when the name says it (\"SKY BUNDESLIGA 4K "
        "[LIVE-EVENT]\" is soccer). Event channels that aren't sports stay untagged.",
    ),
    test_steps=(
        "Start the app: \"Re-sorting sports and events\" runs once in the background and "
        "finishes.",
        "Search \"[EVENT]\": a sports event channel such as \"SKY SPORTS UHD [EVENT]\" "
        "shows the sport label \"Many sports\".",
    ),
)
