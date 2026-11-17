from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=60,
    version="1.0.6",
    date="2026-11-16",
    title="Waiting for a busy source checks less, and learns how long to wait",
    items=(
        "When a source refuses a play because it is still counting a stream you just closed, "
        "StreamSelect now measures how long the source holds on to it: from the moment your "
        "stream closed until a connection is free. Pressing Play again while it waits counts as "
        "the same wait instead of starting the clock over.",
        "Once a source has a few of these on record, the wait stops checking every 30 seconds "
        "from the start. Its first check goes out about a minute before that source usually "
        "frees a connection, and the notice tells you when that will be.",
    ),
    test_steps=(
        "On a one-connection source, play something, close the player and play it again at "
        "once: if it is refused, the notice says \"Waiting for a connection\" and the log says "
        "\"first check in 30 s (typical hold unknown\" the first time.",
        "Press Play again while it waits: the log's \"play 2 of this hold\" shows it is the same "
        "wait. When it starts, the log line \"connection hold on\" gives the time since your "
        "stream closed, the checks and the plays.",
        "After a hold has been recorded, repeat the first step: the notice now says how long the "
        "source usually takes and when the first check is.",
    ),
)
