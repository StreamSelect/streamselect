from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=100,
    version="1.2.0",
    date="2026-11-22",
    title="A short try no longer clears a channel report; choose what right click does in the player",
    items=(
        "Sports: watching a channel you reported (\"Nothing showing\", \"Not this game\") takes "
        "one report back only after 5 minutes, not 1. A quick try of the channel no longer "
        "clears it. Change it in Settings → Sports (All sports) → \"Watching takes a report "
        "back after\".",
        "Settings → Interaction → Player window → Right click: keep the player's own menu "
        "(newer mpv), or have a right click pause and play as it used to. Open player windows "
        "follow straight away. Your own mpv key settings are left alone.",
    ),
    test_steps=(
        "In Sports, report a game's channel as \"Nothing showing\", play it for 2 minutes and "
        "stop: the report mark stays. Play it again for 6 minutes: the mark is gone.",
        "Settings → Sports, All sports: \"Watching takes a report back after: 5 min\" is under "
        "\"What counts as watching\". Pick a sport: the row is not offered per sport.",
        "Settings → Interaction → Right click: \"Pauses and plays\", OK. In an open player "
        "window, right click: it pauses; again: it plays. Set it back to \"Opens the player's "
        "menu\": right click opens mpv's menu.",
        "With \"Pauses and plays\" set, start a new stream: right click pauses in that window too.",
    ),
)
