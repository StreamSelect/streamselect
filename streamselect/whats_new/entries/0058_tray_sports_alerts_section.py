from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=58,
    version="1.0.6",
    date="2026-11-16",
    title="Sports alerts stand apart in the tray menu",
    items=(
        "The tray menu now lists your sports alerts under their own heading, above your "
        "Watch Alerts, each marked with the Sports whistle. Before, a game sat in one "
        "list with guide matches, and several shows airing at once could push it off "
        "the menu entirely.",
        "A show that airs again and again through the evening is now listed once in the "
        "tray menu, at its live or next airing, instead of filling the menu with reruns.",
    ),
    test_steps=(
        "Set an alert on a game starting within 12 hours and have a Watch Alert that "
        "matches a show on now. Open the tray menu: \"Sports alerts\" comes first with the "
        "game and a whistle icon; \"Watch Alerts\" follows with the show.",
        "With a Watch Alert on a show that airs several times tonight, open the tray "
        "menu: the show appears once.",
        "Hide the app to the tray before an alerted game's 15-minute warning: a system "
        "notification appears, and the log says \"Event alert\" and \"sent to the system\".",
    ),
)
