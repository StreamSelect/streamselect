from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=17,
    version="1.0.1",
    date="2026-11-12",
    title="Clearer numbers in a source's Analytics tab",
    items=(
        "What you watch here, Playback and Connections now show each number large, "
        "with what it counts underneath, in even rows instead of a run-on line of "
        "labels and values.",
        "The line about titles only one source carries now reads, for example, "
        "\"17 of the 22 titles you've watched are only available from this source\", "
        "set off so it stands out.",
        "Counts of one read correctly: \"1 film\", not \"1 films\".",
    ),
    test_steps=(
        "Open Sources, choose a source you have watched from, and open its Analytics "
        "tab: What you watch here shows titles watched, plays, watching time and the "
        "rest as large numbers with a caption under each, three to a row.",
        "Below the numbers, a highlighted line says how many of the titles you've "
        "watched are only available from this source.",
        "Playback and Connections show their numbers the same way.",
    ),
)
