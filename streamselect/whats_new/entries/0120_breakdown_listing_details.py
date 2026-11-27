from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=120,
    version="1.3.0",
    date="2026-11-27",
    title="Click an unidentified listing to see its details",
    items=(
        "In Tools ▸ Library Breakdown ▸ Nothing identified, every listing is a link: click "
        "it and the details pane shows that channel, to help work out what it is.",
    ),
    test_steps=(
        "Tools ▸ Library Breakdown ▸ Nothing identified: click a listing under \"Not a "
        "game\": the details pane on the right shows that channel.",
        "Click an example game beside a collection: the details pane shows that channel; "
        "the breakdown stays open.",
        "Click a collection's game count: the channel list opens on that collection's "
        "unidentified listings.",
    ),
)
