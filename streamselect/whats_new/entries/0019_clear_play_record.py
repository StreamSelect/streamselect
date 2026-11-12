from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=19,
    version="1.0.1",
    date="2026-11-12",
    title="Clear History can also forget what source analytics recorded",
    items=(
        "Source analytics keeps its own record of what you play, which Clear History "
        "leaves alone. The Clear History question now has a box to forget that too: "
        "the titles and how long you watched are erased, while whether each play "
        "connected and how fast it started are kept for the Playback figures.",
    ),
    test_steps=(
        "In the History section's menu choose Clear History: the question has an "
        "unticked box about source analytics.",
        "Answer Yes without ticking it, then open a source's Analytics tab: What you "
        "watch here still lists what you played.",
        "Clear History again with the box ticked: What you watch here now says nothing "
        "has been played, and Playback still shows its counts.",
    ),
)
