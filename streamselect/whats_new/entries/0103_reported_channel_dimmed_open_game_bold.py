from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=103,
    version="1.2.0",
    date="2026-11-23",
    title="A reported Sports channel is dimmed, and the open game is bold",
    items=(
        "Sports: a channel whose report counts is drawn slightly dimmer, with its grey flag "
        "saying why. A channel only reported before keeps full strength, its flag and its date.",
        "The game whose channel list you opened is shown in bold, so you can tell which list "
        "belongs to which game. Games you have an alert on stay bold and blue.",
    ),
    test_steps=(
        "In Sports, report a channel \"Nothing showing\": its row dims slightly and its flag "
        "is grey. Hover the flag: the tooltip says how many times and that it is listed last.",
        "A channel reported before (the \"· reported <date>\" row) is not dimmed.",
        "Click a later game: its title turns bold while its list is open, and back to normal "
        "when you close it. A game with an alert stays blue and bold.",
        "Settings → any page: the small group headings in the right-hand help column are "
        "readable, not faint grey.",
    ),
)
