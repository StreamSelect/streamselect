from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=61,
    version="1.0.6",
    date="2026-11-17",
    title="Sports: no empty \"On now\" when nothing is on",
    items=(
        "When no games are on, the Sports view no longer shows an \"On now 0\" band with a "
        "\"Next:\" line. The coming games start right under each sport, so the next game is "
        "simply the first one listed.",
    ),
    test_steps=(
        "Open Sports at a time when no game is on: each sport goes straight to its days "
        "(\"Today\", then the following days), with no \"On now\" band and no \"Next:\" line.",
        "Open it while a game is on: the \"On now\" band and its game cards are there as before, "
        "and it still collapses and expands.",
    ),
)
