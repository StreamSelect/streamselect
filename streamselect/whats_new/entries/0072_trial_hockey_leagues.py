from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=72,
    version="1.0.7",
    date="2026-11-17",
    title="Sports: AHL and Hockeyallsvenskan games, on trial",
    items=(
        "Sports now looks for AHL and Hockeyallsvenskan games as well as NHL games. Both are "
        "on trial while their results are checked against the leagues' schedules.",
        "Some sources list a game's time with no time zone. StreamSelect now works out what "
        "such a collection means from the same source's other collections, using clocks it "
        "has already learned from games whose real time was known. If those collections don't "
        "agree, it does not guess.",
        "A game whose times only come from that kind of reasoning, and whose listings disagree "
        "about when it starts, is shown as less certain.",
    ),
    test_steps=(
        "On an evening with AHL games, open Sports: under Hockey an AHL heading lists them at "
        "their local start time, and the heading shows an AHL chip next to NHL.",
        "Turn on \"Less certain games\": an AHL game whose listings disagree about the start "
        "time, or a Hockeyallsvenskan game listed only once, appears.",
        "In the log after a games refresh: \"Games hockey/AHL: … has no clock of its own; "
        "borrowed -300 min from …\" names the collections it learned from.",
    ),
)
