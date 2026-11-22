from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=96,
    version="1.2.0",
    date="2026-11-22",
    title="Settings pages fit; a live game's bell offers team alerts",
    items=(
        "Settings pages no longer squeeze their contents: labels are no longer drawn under "
        "their values, values are no longer cut off, and a page that is taller than the "
        "window scrolls. The Settings window can now be made much shorter.",
        "Settings ▸ Sports puts a changed value's default and Reset under the value, and "
        "the section list shows every name in full.",
        "Clicking the bell on a game that is already on now offers alerts for either "
        "team's next game or the next time the two meet, instead of an alert for a game "
        "that has already started.",
        "New in Settings ▸ Metadata & API Keys ▸ EPG: how long before the guide runs out a "
        "new one is fetched.",
        "The Discover Browse filter waits until you pause typing before redrawing.",
        "Posters in the trail map that finish loading while it is hidden now show when you "
        "come back to it.",
    ),
    test_steps=(
        "Open Settings ▸ Sports, pick Hockey and change \"Still on\" adds: the default and "
        "Reset appear under the value; no label overlaps a value and no value is cut off.",
        "Make the Settings window as short as it goes: it shrinks well below the old floor, "
        "and the page scrolls.",
        "Check the left list in Settings: \"Recommendations\" and \"Metadata & API Keys\" are "
        "shown in full.",
        "In Sports, click the bell on a live game: a menu offers alerts for each team and for "
        "\"whenever these two meet\", with no alert for this game.",
        "Settings ▸ Metadata & API Keys ▸ EPG shows \"Refresh before it runs out\" at 60 min; "
        "change it, press OK, reopen Settings: the new value is kept.",
        "In Discover, open a shelf's See all and type in Filter: the posters redraw once you "
        "stop typing, not on every letter.",
    ),
)
