from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=83,
    version="1.0.8",
    date="2026-11-18",
    title="Settings: a Sports page for every game timing",
    items=(
        "Settings has a new Sports page. How long games run, which games are listed, how "
        "long alerts and channel reports last, and what counts as watching are all settings "
        "now, each sport with its own values. The way games are found is under Advanced.",
        "A value you change shows its default and a Reset beside it. A value you set stays "
        "as you set it, even if it matches the default.",
        "When an update improves a default you had changed, StreamSelect asks once whether "
        "to keep yours or take the new one. Values you never changed simply move to the new "
        "default. You can turn the question off.",
    ),
    test_steps=(
        "Open Settings ▸ Sports: Hockey is selected, with groups for how long a game runs, "
        "which games are listed, alerts and what counts as watching, and Advanced collapsed.",
        "Change \"Usual length\" to 3 h 00 min: \"default 2 h 45 min\" and Reset appear beside "
        "it. Click OK, then open Sports: a game 2 h 50 min after its start is still on now "
        "rather than likely ending.",
        "Back in Settings ▸ Sports, click Reset on Usual length: it returns to 2 h 45 min and "
        "the default note disappears.",
        "Click \"Advanced — how games are found\": six more settings open below it.",
    ),
)
