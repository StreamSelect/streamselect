from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=81,
    version="1.0.8",
    date="2026-11-18",
    title="Watch Alerts remembers what you collapsed",
    items=(
        "Collapsing a group in Watch Alerts (EPG, Sports, Series, Watching for, Stream "
        "Monitoring) now lasts: it stays collapsed after a restart.",
        "A show you collapse in the EPG group stays collapsed too, instead of opening again "
        "when the app restarts or new airings appear.",
    ),
    test_steps=(
        "In Watch Alerts, click the EPG heading to collapse the group, then restart the app: "
        "EPG is still collapsed. Click it again to open it.",
        "With EPG open, click a show that has several airings to collapse it, then restart: "
        "the show is still collapsed.",
    ),
)
