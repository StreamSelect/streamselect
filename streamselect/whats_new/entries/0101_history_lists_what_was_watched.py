from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=101,
    version="1.2.0",
    date="2026-11-22",
    title="History lists what you watched, not what you skipped",
    items=(
        "When a queue plays through several episodes and you answer No to \"Did you watch "
        "them?\", those episodes are forgotten: they no longer keep the show in History.",
        "An episode or movie you played for less than 5 minutes stays out of History, so "
        "episodes you skipped through are not listed, and a show's row names the last "
        "episode you actually watched. Finished ones always count; live channels are listed "
        "once played. Change it in Settings → Sidebar → History → \"Show in History after\" "
        "(0 lists everything you started).",
    ),
    test_steps=(
        "Queue three episodes of a show you have no History for, let the queue advance past "
        "the first two, close the player and answer No: the show is not in History (or, if "
        "you watched the last one for 5 minutes or more, it names that one).",
        "Answer Yes to the same question on another run: the show is in History, naming the "
        "last episode the queue played through.",
        "Play a movie for about a minute and stop: it is not in History. Play it past 5 "
        "minutes: it is.",
        "Settings → Sidebar: a History group reads \"Show in History after: 5 min\". Set 0 and "
        "OK: the one-minute movie appears in History straight away.",
        "Click the arrow on the History header (\"Explore your full Watch History\"): it "
        "lists the same titles as the sidebar.",
    ),
)
