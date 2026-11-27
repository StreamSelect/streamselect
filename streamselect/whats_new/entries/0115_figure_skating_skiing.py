from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=115,
    version="1.3.0",
    date="2026-11-27",
    title="Figure skating and skiing are recognised",
    items=(
        "Figure skating (free skate, free dance, short program) and skiing (slalom, "
        "downhill, super-G) events now show their sport instead of \"Unknown\".",
        "A figure skating event in a slot named for soccer is figure skating.",
    ),
    test_steps=(
        "Start the app: \"Re-sorting sports and events\" runs once in the background and "
        "finishes.",
        "Search \"Free Skate\": the event rows show the sport \"Figure skating\".",
        "Search \"Slalom\": the event rows show the sport \"Skiing\".",
    ),
)
