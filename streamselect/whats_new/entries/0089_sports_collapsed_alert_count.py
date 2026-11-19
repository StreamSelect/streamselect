from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=89,
    version="1.0.9",
    date="2026-11-18",
    title="Sports: a collapsed day or sport shows its games with alerts",
    items=(
        "When you collapse a day's list or a whole sport, its count shows how many of its "
        "games have an alert set, next to a bell in the alert's colour: \"12 (bell) 1\". "
        "Open, the games themselves show ALERT ON as before.",
    ),
    test_steps=(
        "Set an alert on a game listed under Tomorrow, then collapse Tomorrow: its count "
        "reads the number of games, a blue bell, and 1.",
        "Expand it again: the count is the plain number, and the game shows ALERT ON.",
        "Collapse the whole sport: its header count shows the bell and 1 too.",
        "Collapse a day with no alerts: its count stays a plain number.",
    ),
)
