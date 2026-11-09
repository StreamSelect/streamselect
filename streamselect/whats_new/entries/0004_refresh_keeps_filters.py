from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=4,
    version="1.0.1",
    date="2026-11-09",
    title="A refresh no longer turns on Language and Region filters",
    items=(
        "When a refresh brought back languages, regions or other filter values that had been "
        "missing for a while, the filter panel treated them as switched off and saved that. "
        "Language and Region filters you never set then appeared on every search. Values that "
        "come back now keep the setting they had before.",
        "If these filters already appeared for you, click All in the filter panel once to clear "
        "them.",
    ),
    test_steps=(
        "Click All in the filter panel: no Language or Region filter chips show above the list.",
        "Refresh a source from the sidebar Sources button and wait for it to finish: still no "
        "Language or Region chips appear.",
        "Quit and start the app again: the search bar still shows no filter chips you didn't add.",
        "Untick one language, refresh the source: that language stays unticked and its chip "
        "remains.",
    ),
)
