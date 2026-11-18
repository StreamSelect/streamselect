from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=76,
    version="1.0.7",
    date="2026-11-18",
    title="Sports: counts show only games on now or still to come",
    items=(
        "A league's heading no longer counts its finished games: the number is the games on "
        "now or still to come.",
        "Each sport's heading now shows how many of its games, across all its leagues, are on "
        "now or still to come.",
    ),
    test_steps=(
        "Open Sports on an evening with some games already finished: each league's chip counts "
        "only the games on now and still to come, not the finished ones listed under Finished.",
        "Beside the sport's name (e.g. Hockey) a count chip shows the total of those games "
        "across its leagues; it is hidden when there are none.",
    ),
)
