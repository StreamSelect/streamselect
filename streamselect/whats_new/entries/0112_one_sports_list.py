from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=112,
    version="1.2.1",
    date="2026-11-27",
    title="Sports channels are sorted by one list",
    items=(
        "The app now recognises sports from one list of sports, leagues and their names, "
        "so a channel's sport and league always agree: a league is never shown under "
        "another sport.",
        "Sports channels that used to say \"Unknown\" now say what they are: \"Many "
        "sports\" for channels like Sky Sports or beIN, \"Event slot\" for numbered event "
        "feeds with nothing on, and \"Unknown\" only for a game nothing identified.",
        "A league named in a listing decides its sport (\"Football: NFL …\" is American "
        "football), and a listing's own name counts before its collection's.",
        "An event slot's own name (\"SOCCER PPV 80\") no longer decides the sport of what "
        "it shows: an NFL special in that slot is American football.",
        "College basketball listings marked flohoops, golf, MMA and cycling channels are "
        "now recognised.",
        "Channels are re-sorted once, in the background, the first time the app starts.",
    ),
    test_steps=(
        "Start the app: \"Re-sorting sports and events\" runs once in the background and "
        "finishes.",
        "Channels: search \"Sky Sports\": the rows' sport label says \"Many "
        "sports\", not \"Unknown\".",
        "Search \"NO EVENT\": the empty slots say \"Event slot\".",
        "Search \"NFL\": a listing such as \"Football: NFL …\" says American football, with "
        "the NFL league.",
        "Sports view: hockey and basketball are still listed in the same order with "
        "their games.",
    ),
)
