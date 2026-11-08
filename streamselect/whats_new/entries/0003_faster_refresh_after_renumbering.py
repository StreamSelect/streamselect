from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=3,
    version="1.0.1",
    date="2026-11-07",
    title="Faster source refresh when a source reorders its list",
    items=(
        "When a source shifts the position numbers of its channels, a refresh no longer treats "
        "every channel as changed. Only renamed channels are re-read, so the refresh finishes "
        "minutes sooner.",
        "Fixed a refresh step that could stop partway on a very large source, which left some "
        "renamed channels showing their old titles in the details panel.",
    ),
    test_steps=(
        "Refresh a large source from the Sources page: it completes, and the log line "
        "'Refreshed …: N channels in …' shows a shorter store time than before.",
        "After the refresh, open a live event channel whose name changed today: the details "
        "panel title matches the name in the channel list.",
        "Search the log for 'too many SQL variables': it does not appear for this refresh.",
    ),
)
