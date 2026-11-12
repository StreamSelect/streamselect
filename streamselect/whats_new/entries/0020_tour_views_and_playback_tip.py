from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=20,
    version="1.0.1",
    date="2026-11-12",
    title="The tour says which view to use, and the first play explains the playback line",
    items=(
        "The tour's top bar card now says when to use each view: Search when you know "
        "what you want, Discover to browse, and Recipe to narrow everything down. Its "
        "Search card mentions \"Filter these results\" for narrowing what's listed.",
        "When the tour ends, it reminds you that hovering over any button tells you "
        "what it does.",
        "The first time something starts playing, a tip points at the playback line at "
        "the top: click it for the audio track, subtitles, Normalize volume and "
        "Downmix audio (mono for one speaker, stereo for headphones).",
    ),
    test_steps=(
        "Choose Tools ▸ Take the tour: the top bar card names Search, Discover and "
        "Recipe and when to use each, and the Search card mentions \"Filter these "
        "results\".",
        "Finish the tour: the message at the end says to hover over any button to see "
        "what it does.",
        "On a profile that has not seen it, play a channel: once the picture moves, a "
        "tip rings the playback line at the top, and it does not appear again on the "
        "next play.",
    ),
)
