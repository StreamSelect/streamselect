from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=108,
    version="1.2.0",
    date="2026-11-23",
    title="Jumping back to the start no longer drops a show from History",
    items=(
        "History now counts the furthest point you reached in an episode or film, not just "
        "where you stopped. Watch nine minutes, jump back to see the opening again, and stop: "
        "it stays in History. Resume still picks up where you actually stopped.",
    ),
    test_steps=(
        "Play an episode you have not watched for 6 minutes, jump back to the start, and stop "
        "within a minute: it is in History, and its Resume shows where you stopped.",
        "Mark that episode unwatched: it leaves History.",
    ),
)
