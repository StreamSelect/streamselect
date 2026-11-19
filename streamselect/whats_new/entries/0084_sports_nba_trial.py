from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=84,
    version="1.0.8",
    date="2026-11-18",
    title="Sports: basketball, with the NBA on trial",
    items=(
        "The Sports view now finds NBA games, under a Basketball section of its own beside "
        "Hockey. The NBA is on trial while its games are checked against the real schedule.",
        "Basketball has its own values in Settings ▸ Sports: its games are shorter than "
        "hockey's, so a game shows as likely ending and as finished sooner.",
        "Team names with a number in them, like the Philadelphia 76ers, keep the number.",
    ),
    test_steps=(
        "Open Sports on an evening with NBA games: a Basketball section with its basketball "
        "icon lists NBA games, next to Hockey.",
        "Find a Philadelphia 76ers game: the name reads \"Philadelphia 76ers\", not "
        "\"Philadelphia Ers\".",
        "Open Settings ▸ Sports and pick Basketball: Usual length is 2 h 30 min and Longest a "
        "game runs is 3 h 15 min. Pick Hockey: still 2 h 45 min and 3 h 30 min.",
        "Change Basketball's Usual length and click OK: Hockey's is unchanged when you go back.",
    ),
)
