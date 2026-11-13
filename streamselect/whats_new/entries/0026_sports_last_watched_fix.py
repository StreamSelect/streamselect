from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=26,
    version="1.0.2",
    date="2026-11-12",
    title="Sports plays the channel you actually watched, not one you tried for a few seconds",
    items=(
        "With no preferred channel, a game card plays the channel you last watched that "
        "league on. A try of under a minute no longer counts, so a channel you bailed on "
        "does not become the default.",
        "The cards update their channel as soon as you start playing something, instead of "
        "keeping the order from when the view opened.",
        "Station names written in small superscript letters (like \"ᴳᴼᴸᴰ ᴿᴬᵂ\") show in "
        "normal letters.",
    ),
    test_steps=(
        "In Sports, open a live game and play one channel for a few seconds, then another "
        "for over a minute: the card's ▶ line names the one you watched for over a minute.",
        "Open a game whose channel list includes a superscript-named collection: it reads "
        "in normal-size letters.",
    ),
)
