from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=127,
    version="1.4.0",
    date="2026-11-27",
    title="Discover's categories, tidied",
    items=(
        "Category names lose the region in front of them (\"UK| NETFLIX ORIGINAL\" is "
        "\"NETFLIX ORIGINAL\"); the region shows as a small chip after the name instead. A "
        "country name in front (\"DENMARK DISNEY+ PPV\") is read the same way.",
        "Discover's More Categories lists films and series. Live TV packages (sports, news, PPV "
        "slots) were most of that list; the new \"Live categories\" switch beside More "
        "Categories brings them back, and is remembered.",
        "Categories spelled almost the same are one shelf: \"HORROR / THRILLER\", "
        "\"HORROR/THRILLER\" and \"HORROR/THRILLERS\" together, with each region they come from.",
        "The provider's own category names are kept exactly as they were; search and the "
        "details pane still open the provider's category itself.",
    ),
    test_steps=(
        "Start the app and let the one-time re-read finish (Tools ▸ Migration Center).",
        "Discover ▸ More Categories: names have no \"XX|\" in front; a shelf shows region "
        "chips after its name (hover one: the region's full name).",
        "There is no live-package shelf (e.g. \"MAX PPV VIP\"). Click \"Live categories\": they "
        "appear after a reload. Restart: the switch is as you left it.",
        "Open the \"HORROR / THRILLER\" shelf: films filed under each spelling are there.",
    ),
)
