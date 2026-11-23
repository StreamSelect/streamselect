from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=103,
    version="1.2.0",
    date="2026-11-23",
    title="A reported Sports channel's flag is easier to spot",
    items=(
        "Sports: the flag on a channel you reported, while the report counts, is now a muted "
        "amber instead of grey, so it stands out without shouting. A channel only reported "
        "before keeps a grey flag and its date.",
    ),
    test_steps=(
        "In Sports, report a channel \"Nothing showing\": its flag is a soft amber, on the row "
        "and on the game's card. Switch theme (Style menu) to Daylight and back: it stays "
        "amber and readable in each.",
        "A channel reported before (the \"· reported <date>\" row) has a grey flag.",
        "Settings → any page: the small group headings in the right-hand help column are "
        "readable, not faint grey.",
    ),
)
