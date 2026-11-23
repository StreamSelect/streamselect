from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=99,
    version="1.2.0",
    date="2026-11-22",
    title="Live channels can start with subtitles off; resume works in every player mode",
    items=(
        "New \"Subtitles off on live channels\" switch, in the playback menu (click the "
        "playback readout in the header) and in Settings → Playback. Live captions are typed "
        "as the broadcast airs, so they lag. With it on, live channels and Sports games "
        "start with no subtitles; movies and series keep theirs. It is remembered.",
        "Resuming a movie or episode now starts where you left off when Player mode opens a "
        "new window for each play, and when the shared player window fails to start. Both "
        "used to start from the beginning.",
    ),
    test_steps=(
        "Play a live channel that shows subtitles. Click the playback readout and tick "
        "\"Subtitles off on live channels\". Play another live channel (or a game from "
        "Sports): it starts with no subtitles, and the menu's Subtitles list says Off.",
        "With the switch on, play a movie that has subtitles on by default: they still show.",
        "Restart the app: the switch is still ticked, in the menu and in Settings → Playback.",
        "Set Settings → Playback → Player mode to a new window per play, then resume a "
        "half-watched movie: it starts at the saved position, not at 0:00.",
    ),
)
