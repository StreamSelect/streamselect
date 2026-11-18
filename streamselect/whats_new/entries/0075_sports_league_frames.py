from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=75,
    version="1.0.7",
    date="2026-11-18",
    title="Sports: each league gets its own heading and frame",
    items=(
        "When a sport has games from more than one league, each league now has a larger, "
        "centred heading with its logo, and its games on now, games to come and finished games "
        "sit together in a frame beneath it. Click the heading to collapse or expand the league.",
        "The league's chip shows how many games it has and how many are on now. When none are "
        "on, it shows when the next one starts instead.",
        "The cards for games on now are centred.",
        "\"On now\" and \"Finished\" no longer show a count.",
    ),
    test_steps=(
        "With \"Less certain games\" on and games from two leagues listed (for example NHL and "
        "AHL), open Sports: each league has a centred heading over a framed section holding "
        "its own On now, days and Finished.",
        "On a league with no game on now, the chip beside its name reads the game count, the "
        "live mark and the next start time, e.g. \"3 (•) 7:00 PM\". On a league with games on, "
        "it reads the count, the live mark and how many are on.",
        "Click a league's heading: its frame collapses; click again to bring it back. Restart "
        "the app: it stays as you left it.",
        "The On now cards sit centred in the space; \"On now\" and \"Finished\" show no count.",
    ),
)
