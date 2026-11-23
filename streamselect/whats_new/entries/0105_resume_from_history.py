from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=105,
    version="1.2.0",
    date="2026-11-23",
    title="History resumes where you left off, and rewatching keeps your place",
    items=(
        "Episodes opened from History, Watch Later (the queue) or Favorites now resume where "
        "you stopped, as Settings → Playback says (or start over, if you chose that there). "
        "They always started from the beginning before.",
        "Right-click a show in History: Play plays the episode the row names, and \"Resume "
        "from …\" / \"Play from Beginning\" are offered for it.",
        "Starting a finished episode or movie again no longer marks it unwatched or drops it "
        "from History. Stop partway and it keeps its watched mark and gains a resume point.",
        "In the details pane, the button beside \"Resume 16:27\" now says \"Start over\", so "
        "the episode code no longer gets cut off.",
    ),
    test_steps=(
        "Play an episode for a few minutes and stop. In History, double-click the show: it "
        "resumes there. Settings → Playback → choose start from the beginning; double-click "
        "again: it starts at 0.",
        "Right-click that show in History: \"Play from …\" (or \"Resume from …\") and \"Play "
        "from Beginning\" are there and each does what it says for that episode.",
        "Open an episode you finished; play it for 30 seconds and stop: it still shows the "
        "watched tick, it is still in History, and the details pane offers Resume 0:30.",
        "Select an episode with saved progress in a series: the buttons read \"Start over\" "
        "and \"Resume M:SS\", both whole.",
    ),
)
