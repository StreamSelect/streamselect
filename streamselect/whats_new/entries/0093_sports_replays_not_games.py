from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=93,
    version="1.1.0",
    date="2026-11-19",
    title="Sports: replays are no longer shown as games",
    items=(
        "Reruns of last night's games, such as the morning NBA airings on European channels, "
        "are recognised as replays instead of showing as less certain games.",
        "A team can't play two games at once: when two listings overlap with the same team, "
        "the better-supported one is kept and the other is treated as a replay.",
        "Guide shows dated another day, like a weekly magazine programme, are no longer "
        "attached to a game as a channel showing it.",
        "New Advanced settings in Settings ▸ Sports say how far from a league's usual start "
        "times a guide-only game counts as a replay.",
    ),
    test_steps=(
        "Turn on \"Less certain games\" in Sports in the morning: last night's NBA games airing "
        "on European channels are not listed.",
        "Tonight's real games are listed as before, confirmed games unchanged.",
        "Settings ▸ Sports ▸ Advanced: three new rows about usual start times, at 3 h, "
        "5 confirmed games and 30 days.",
    ),
)
