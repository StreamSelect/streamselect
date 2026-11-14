from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=44,
    version="1.0.4",
    date="2026-11-14",
    title="Sports: games grouped by start time",
    items=(
        "Later and finished games line up in a time column, grouped by start time with the "
        "time shown once; every other group has a faint tint. Hover a game to see its own time.",
        "Today's games are headed Today, not Tonight.",
        "The league is named once, in the sport's header, instead of on every game. A sport "
        "with more than one league gets a heading for each.",
        "A game you have an alert on has its title in the same blue, bold look as a watch-list "
        "match in the TV guide.",
        "By sport / By time: list each sport on its own, or every sport together by start "
        "time with each game naming its sport and league.",
    ),
    test_steps=(
        "Open Sports on a day with several games at the same time: the time shows once for "
        "the group, titles all start at the same place, and every other group is faintly "
        "tinted.",
        "Hover a game below the first in its group: its time appears, muted, to the left.",
        "Today's day heading reads Today · and the date; no row says NHL.",
        "Turn on an alert for a team from a game's bell: that game's title turns blue and "
        "bold, with ALERT ON beside it.",
        "Click By sport at the top: it switches to By time, one list for every sport where "
        "each game names its sport and league. Click again to go back.",
    ),
)
