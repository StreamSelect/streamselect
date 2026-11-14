from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=50,
    version="1.0.4",
    date="2026-11-14",
    title="Sports: a game's channel list says which channel is which",
    items=(
        "A regular TV channel is listed by its own name (TV3 Sport, NBC West, ESPN 4), not "
        "the package it sits in; a channel made for one event keeps its package's name.",
        "Quality words in a package's name (\"HD & HEVC\", \"VIP RAW\") are chips now. HEVC "
        "and RAW sit right after the channel name; region, EPG, the quality tier and the frame "
        "rate each have their own column.",
        "Once you've played a channel, it shows the audio language and frame rate the stream "
        "really had, with the measured mark. A language is never guessed from the country.",
        "Two channels that would read the same get a short note telling them apart, and "
        "PREFERRED sits right after the channel's name.",
        "Collection names everywhere drop quality words joined with \"&\" or written in small "
        "superscript letters: \"SPORT HD & HEVC\" reads \"SPORT\". This is redone once, in the "
        "background, the first time the app starts.",
    ),
    test_steps=(
        "Open a live game's channels in Sports: regular channels show their own names, HEVC or "
        "RAW chips follow the name, and region, EPG, tier and FPS each line up in a column.",
        "Play one of the game's channels for a few seconds, then reopen the list: that row "
        "leads with a measured language chip and shows a measured FPS chip.",
        "Find two rows from the same package: each has a short note, or #1 and #2, telling "
        "them apart, and neither note repeats a chip.",
        "Make a channel PREFERRED: the chip sits right after its name.",
    ),
)
