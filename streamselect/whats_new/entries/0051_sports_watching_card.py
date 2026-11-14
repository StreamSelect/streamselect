from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=51,
    version="1.0.4",
    date="2026-11-14",
    title="Sports: the card you're watching says WATCHING",
    items=(
        "The card of the game you're watching gets a thicker green outline and says "
        "\"WATCHING\". The channel's name leaves the card; open the card and the channel is "
        "the green row in its list.",
        "Open, the card adds what the stream is doing right now: its video bitrate, live from "
        "the player and averaged over a few seconds, then its quality and frame rate.",
    ),
    test_steps=(
        "Play a live game from Sports: its card turns a thicker green and reads ▶ WATCHING "
        "with no channel name; other cards are unchanged.",
        "Open that card: WATCHING is followed by a bitrate (for example 6.6 Mb/s), the "
        "quality and the frame rate, and the bitrate changes gently as you watch.",
        "Close the card: only WATCHING and the +N chip remain.",
    ),
)
