from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=52,
    version="1.0.5",
    date="2026-11-16",
    title="StreamSelect can keep running in the system tray",
    items=(
        "Close the window and StreamSelect can stay in the system tray (the menu bar on "
        "macOS), still checking your Watch Alerts, game alerts and updates. The first time "
        "you close it, it asks whether to keep running; Settings ▸ System Tray changes "
        "the answer.",
        "While it's in the tray, alerts arrive as system notifications. Click one to open "
        "StreamSelect where it points: Sports for a game, the guide for a Watch Alert. "
        "Settings ▸ System Tray chooses which kinds you get.",
        "The tray menu shows what's playing, with Stop playback, and your alerted games "
        "and programmes for the next 12 hours, live ones first. It can also pause "
        "notifications, check for updates, and quit.",
        "A stream keeps playing when you close the window. File ▸ Exit and Quit in the "
        "tray menu still quit completely.",
        "On a desktop with no system tray, the setting is greyed out and closing the "
        "window quits as before.",
    ),
    test_steps=(
        "Close the main window with its close button: a question asks \"Keep StreamSelect "
        "running in the system tray?\". Choose Keep running: the window goes, a tray icon "
        "stays, and a notification says StreamSelect is still running.",
        "Left-click the tray icon (Windows, Linux): the window comes back. Click it again: "
        "it hides. On macOS, clicking the menu-bar icon opens its menu.",
        "Play a channel, then close the window: the stream keeps playing. Open the tray "
        "menu: Playing lists the channel, and Stop playback stops it.",
        "Set a game alert from Sports on a game starting within 12 hours: the tray menu "
        "lists it under Your alerts. Choose it: the window opens on Sports.",
        "With the window in the tray, wait for an alert to start: a system notification "
        "appears. Click it: the window opens on Sports (game) or the guide (Watch Alert).",
        "Tray menu ▸ Pause notifications ▸ For 1 hour: the icon's tooltip says notifications "
        "are paused until a time an hour from now, and no notification appears. "
        "Choose Resume notifications to end the pause.",
        "Settings ▸ System Tray: untick \"Keep StreamSelect in the system tray…\" and click OK: "
        "the tray icon goes, and closing the window quits.",
        "Tray menu ▸ Quit StreamSelect: the app quits, asking first only if a recording is due.",
    ),
)
