from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=140,
    version="1.5.0",
    date="2026-11-28",
    title="Featured actor rows find their films; row arrows show on hover",
    items=(
        "Discover's featured actor row now finds every film and series featuring that person, "
        "the same way clicking their name in a title's details does. It only searched series "
        "before, so Clint Eastwood showed one title (Rawhide) out of 78.",
        "The ← → arrows on an open row show only while the pointer is over that row.",
    ),
    test_steps=(
        "Discover ▸ Featured: <actor>: the row holds their films as well as series (Clint "
        "Eastwood: The Good, the Bad and the Ugly, Unforgiven, Gran Torino…).",
        "Move the pointer over an open row that scrolls: → appears at its right edge (← once "
        "scrolled). Move away: both disappear.",
    ),
)
