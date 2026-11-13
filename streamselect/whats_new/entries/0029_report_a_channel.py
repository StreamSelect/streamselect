from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=29,
    version="1.0.2",
    date="2026-11-13",
    title="Tell the app a channel didn't play or showed the wrong thing",
    items=(
        "Right-click a channel in a Sports event: under \"Report this channel\" choose Didn't "
        "play or Wrong content. That channel is listed last for the league's events, with a "
        "small flag that says why when you hover it, so a card never plays it by default "
        "while another channel is available.",
        "A report lasts 30 days; more reports keep it longer. Watching the channel for a "
        "while afterwards cancels a report, and \"Clear bad reports\" removes them.",
        "The same right-click menu also plays the channel, makes it PREFERRED and hides it.",
    ),
    test_steps=(
        "In Sports, open a live event, right-click its first channel and choose Didn't play: "
        "it moves to the bottom of the list with a flag; hover the flag: it says reported once.",
        "Right-click it again: Clear bad reports is enabled; choose it: the flag goes away.",
        "Right-click a channel and choose Wrong content: it moves to the bottom for this event "
        "only; open another event from the same collection: that channel is not flagged there.",
    ),
)
