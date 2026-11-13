from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=25,
    version="1.0.2",
    date="2026-11-12",
    title="Sports: each game's channels inside its card, a preferred channel, and hiding bad ones",
    items=(
        "Each game card shows a progress bar instead of \"1h 6m in\" (hover it for the start and "
        "the usual end time) and names the channel it plays. Click that line to play it, or "
        "double-click anywhere on the card.",
        "The chip with the live mark and \"+N\" opens the card to list every other channel "
        "showing the game. Click a channel's name to play it.",
        "Hover a channel to make it your PREFERRED channel for that league; the card then plays "
        "it first for every game it carries. With none chosen, the card plays the channel you "
        "last watched that league on.",
        "Hide a channel (or a whole collection) from a league's games with the eye; hidden "
        "channels are counted on the card and can be brought back.",
        "While you watch, the card says PLAYING in green next to the channel, and its row is "
        "marked without moving.",
        "Section headers stand out and fold; Finished starts folded. Sort On now by earliest or "
        "latest start, and turn on \"Less certain games\" to also see games only one collection "
        "lists (dashed outline). These choices are remembered.",
        "Right-click a live game to mark it finished. The view never scrolls sideways any more.",
    ),
    test_steps=(
        "During an NHL game open Sports: each card shows LIVE, \"started …\", a progress bar "
        "(hover: start and usual end time), the league, and \"▶ [country] channel\" with a "
        "\"+N\" chip; narrow the window: cards wrap, no sideways scroll bar.",
        "Click the ▶ line: that channel plays. Double-click a card elsewhere: the same channel plays.",
        "Click the +N chip: the card moves to the top at full width and lists every channel; "
        "click a channel name: it plays, the card's top line reads PLAYING in green and the row "
        "turns green in place.",
        "Hover a channel and click its dashed PREFERRED chip: it turns solid, and the card's ▶ "
        "line now names that channel. Click it again: cleared.",
        "Hover a channel, click the eye, choose \"Hide this channel from NHL games\": it leaves "
        "the list and \"1 hidden channel · show\" appears; click show, then the eye on it: it is back.",
        "Click Finished's header: its games appear; restart the app: it stays as you left it. "
        "Click \"Earliest first\": it reads \"Latest first\" and the cards reverse.",
        "Right-click a live card and choose Mark as finished: it moves under Finished.",
    ),
)
