from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=109,
    version="1.3.0",
    date="2026-11-23",
    title="\"How many did you watch?\" — three buttons, and only at night",
    items=(
        "When the queue has played on through episodes and the player closes, the app now "
        "asks \"How many did you watch?\" with three buttons: None, First only, All. None puts "
        "the first episode and the rest back to unwatched; First only keeps the first; All "
        "keeps them all (Enter picks All). Closing the window leaves them as they were.",
        "By default it only asks when the queue played at some point between 9 PM and 5 AM, "
        "when you might have fallen asleep — a run started at 7 PM that carried on past 9 "
        "counts. Change the hours, or ask at any time, in Settings → Sidebar → "
        "History (\"Ask how many episodes you watched\" and \"Ask when\").",
        "The question is no longer cut off at the top.",
    ),
    test_steps=(
        "Before 9 PM, play an episode with the rest of the season queued and let the queue "
        "carry on past 9 PM, then close the player: \"How many did you watch?\" appears.",
        "After 9 PM, play an episode with the rest of the season queued, let it move on to the "
        "next, and close the player: \"How many did you watch?\" appears, in full, with None · "
        "First only · All.",
        "Choose First only: the first episode stays watched, the next goes back to unwatched "
        "and leaves History. Repeat and choose None: both go back. Choose All: both stay.",
        "Settings → Sidebar → History: set \"Ask when\" to hours that exclude now; repeat the "
        "run: no question. Set it to \"at any time\": the question comes back.",
    ),
)
