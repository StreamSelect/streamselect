from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=117,
    version="1.3.0",
    date="2026-11-27",
    title="Library breakdown: how your sports channels are sorted",
    items=(
        "Tools ▸ Library Breakdown shows how the app sorted your sports, PPV and event "
        "channels: every sport, how each was decided (its name, a league, its teams, or a "
        "guess), each sport's leagues, and the teams the Sports view has learned.",
        "The Nothing identified tab lists what no rule could sort: games two leagues fit, "
        "games between teams no list knows (by collection), and listings that aren't games.",
        "Click a sport or league to see its leagues or teams; click a count or a tile to "
        "open those channels. Only your enabled sources are counted.",
    ),
    test_steps=(
        "Tools ▸ Library Breakdown: the Sports tab opens on hockey, with its leagues and "
        "the NHL's teams on the right; confirmed teams come first.",
        "Click Soccer: the right column shows soccer's leagues.",
        "Click soccer's channel count: the channel list opens on those channels.",
        "Back, then reopen it and pick the Nothing identified tab: the four tiles add up, and "
        "the collections list ends in Show all.",
    ),
)
