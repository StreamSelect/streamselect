from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=53,
    version="1.0.5",
    date="2026-11-16",
    title="Tray alerts: a badge on the app's own icon, and live games play from the menu",
    items=(
        "When an alert arrives while StreamSelect is in the tray, its icon keeps the app's "
        "look and gains a red \"!\" badge, instead of turning into a generic notification "
        "icon. The badge stays until you open the tray menu or the window.",
        "Choosing a LIVE game or programme in the tray menu opens StreamSelect on it and "
        "starts playing it: a game plays on your preferred channel, the one its Sports card "
        "lists first. An upcoming one only opens the app, as before.",
        "Clicking a system notification about new episodes of a series opens that series' "
        "details, and one about a new Watch Alert match (a movie, say) shows that alert's "
        "matches, the same as clicking it in Watch Alerts. New matches now reach the system "
        "from the tray too.",
    ),
    test_steps=(
        "Close the window to the tray, then wait for a game alert or Watch Alert to "
        "start: the tray icon is still the StreamSelect icon, now with a red \"!\" in "
        "its lower-right corner, both while the notification shows and after it goes.",
        "Open the tray menu (or click the icon to show the window): the badge goes.",
        "The first \"StreamSelect is still running\" notice does not add the badge.",
        "With an alerted game on now, open the tray menu: its row has a play icon and "
        "reads LIVE. Choose it: the window opens on Sports and the game starts playing on "
        "the channel its card lists first.",
        "Choose an upcoming game in the tray menu: the window opens on Sports and "
        "nothing starts playing.",
        "With the window in the tray, wait for a monitored series to get new episodes and "
        "click the notification: the window opens on that series' details.",
    ),
)
