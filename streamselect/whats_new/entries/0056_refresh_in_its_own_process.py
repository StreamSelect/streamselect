from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=56,
    version="1.0.5",
    date="2026-11-16",
    title="StreamSelect stays smaller while it runs",
    items=(
        "Refreshing a source now happens in a separate background process that ends "
        "when the refresh does. Before, each refresh left StreamSelect about 250 MB "
        "larger for as long as it ran, because the memory used to read the channel "
        "list was never handed back.",
        "Posters kept in memory are now capped at 64 MB. They stay full size, so the "
        "details pane and previews look the same; the oldest are dropped first.",
    ),
    test_steps=(
        "Refresh a source (its Refresh button in Sources): the progress steps and the "
        "result read as before, and the channel list updates when it finishes.",
        "While it refreshes, a system monitor shows a second StreamSelect process; it "
        "goes away when the refresh finishes, and the main one doesn't grow by "
        "hundreds of MB.",
        "Quit StreamSelect during a refresh: it quits, the second process goes too, "
        "and the next launch refreshes normally.",
        "Browse Discover for a while, then open a poster in the details pane and resize "
        "the pane: the poster stays sharp.",
    ),
)
