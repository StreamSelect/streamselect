from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=1,
    version="1.0.0",
    date="2026-11-07",
    title="StreamSelect",
    items=("A lean, native desktop app for organizing and playing your own streams and "
           "media, with multiple sources, a watch queue, recommendations and an mpv player.",),
    test_steps=("Launch the app — the main window opens and the StreamSelect logo appears in "
                "the window and task bar.",
                "Add a source, play something and click the playback readout in the header — "
                "the menu shows the queue, tracks and playback settings.",),
)
