from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=33,
    version="1.0.2",
    date="2026-11-13",
    title="Sports games you set an alert on appear in Watch Alerts",
    items=(
        "Watch Alerts has a Sports group, right under EPG. It lists each game you set the bell "
        "on, live or coming up, with a progress bar while it is on and the time until it starts "
        "before that. Double-click one to play it.",
        "A game leaves the list by itself once it is over or you start watching it. A bell set "
        "for a team or a matchup keeps listing their next games, each as its own row.",
        "The Watch Alerts header now shows one green badge per kind of alert, each with its own "
        "icon: movies, series and sports. Click a badge to jump to that group.",
        "A bell set for one game only is deleted once that game is over, instead of staying "
        "behind.",
        "The tour has a Watch Alerts stop explaining the three badges.",
    ),
    test_steps=(
        "In Sports, click the bell on an upcoming game: Watch Alerts shows a Sports group under "
        "EPG with that game and the time until it starts.",
        "Set a bell on a game that is on now: its Sports row shows a progress bar instead of a "
        "time. Double-click the row: the game plays, and within a minute the row goes.",
        "With a sports alert waiting, the Watch Alerts header shows a green badge with the "
        "sports icon and a number, with no plus sign. Collapse the Sports group, then click the "
        "badge: the group opens.",
        "Tools ▸ Take the tour: a Watch Alerts stop lists the movie, series and sports badges "
        "with their icons.",
    ),
)
