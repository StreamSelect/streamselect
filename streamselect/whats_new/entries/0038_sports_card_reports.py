from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=38,
    version="1.0.3",
    date="2026-11-13",
    title="Report a game's channel from its card",
    items=(
        "Right-click a game that is on now in Sports to report its channel: \"No picture\" when "
        "nothing comes up, or \"Not this game\" when something else is showing. Until now a "
        "game with only one channel had no way to report it.",
        "The same two choices replace \"Didn't play\" and \"Wrong content\" on a game's "
        "channel rows.",
    ),
    test_steps=(
        "Open Sports while a game is on. Right-click its card: the menu offers Mark as "
        "finished, then No picture and Not this game.",
        "Choose No picture, then open the card's channel list (+N): that channel is last, "
        "with a flag whose tooltip says no picture.",
        "Right-click a channel row in an open card: the reports read No picture and Not this "
        "game, with no \"Report this channel\" heading.",
        "Right-click an upcoming game's card: no menu opens.",
    ),
)
