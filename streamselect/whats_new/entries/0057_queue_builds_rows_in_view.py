from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=57,
    version="1.0.5",
    date="2026-11-16",
    title="A long Watch Queue no longer weighs the app down",
    items=(
        "The Watch Queue in the sidebar now draws only the rows near what you can see, "
        "and draws more as you scroll. A queue of several hundred titles used to build "
        "every row at launch, which took tens of MB of memory and more than half of "
        "everything the app had on screen. It looks and behaves the same: the filter "
        "still searches the whole queue, and the scrollbar is right from the start.",
    ),
    test_steps=(
        "With a long Watch Queue, open the app: the queue shows its rows as before, "
        "with no blank rows.",
        "Scroll the queue quickly to the bottom: every row you land on is drawn, and the "
        "scrollbar doesn't jump.",
        "Find in queue (the magnifier in its header) and type part of the oldest title's "
        "name: it appears, drawn normally.",
        "Make the sidebar section taller by dragging its edge: the new rows that come "
        "into view are drawn.",
    ),
)
