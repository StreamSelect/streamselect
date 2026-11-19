from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=86,
    version="1.0.8",
    date="2026-11-18",
    title="Sports: hide a league with its chip",
    items=(
        "The league chips in a sport's header now sit on the right. Click one to hide that "
        "league from the list below; click it again to show it. A hidden league's chip is "
        "dashed and greyer, and still shows how many of its games are on now.",
        "Hidden leagues are remembered, and the sport's game count leaves them out. "
        "Clicking anywhere else on the header still collapses the sport.",
    ),
    test_steps=(
        "Open Sports: Hockey's league chips sit on the right of its header, apart from the "
        "name.",
        "Click the AHL chip: the AHL banner and its games disappear, the chip turns dashed "
        "and grey, Hockey stays open, and its count drops by the AHL's games.",
        "Restart the app and open Sports: the AHL is still hidden. Click its chip: it comes "
        "back.",
        "Hide every Hockey league: Hockey shows \"All leagues hidden. Click a league to show "
        "it.\"",
    ),
)
