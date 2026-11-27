from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=113,
    version="1.3.0",
    date="2026-11-27",
    title="Event channels show the sport of the game they carry",
    items=(
        "A sports channel that doesn't say its sport (an event slot, a channel like "
        "Sky Sports that carries many sports, or a game listing nothing identified) now "
        "shows the sport and league of the game on it now, or of its next game today.",
        "Hover the sport to see which game it came from. When the channel carries no "
        "game, it reads as before.",
    ),
    test_steps=(
        "Sports view: note a game on now or later today and one of its channels whose name "
        "doesn't say the sport (for example an event slot).",
        "Channels: search that channel's name: its sport label shows the game's sport and "
        "league, not \"Event slot\", \"Many sports\" or \"Unknown\".",
        "Hover the sport label: the tooltip names the game and says the channel itself is "
        "listed as an event slot, many sports or unknown.",
        "Search \"NO EVENT\": empty slots still say \"Event slot\".",
    ),
)
