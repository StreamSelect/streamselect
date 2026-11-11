from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=6,
    version="1.0.1",
    date="2026-11-11",
    title="Netflix, Prime and Apple TV+ folders count toward their platform",
    items=(
        "A source folder named after a streaming service plus something else, such as "
        "\"NETFLIX KIDS\", \"NETFLIX CHRISTMAS\", \"AMAZON PRIME 4K\" or \"APPLE TV+\", was not "
        "counted as that service. Those titles now count under Netflix, Amazon Prime or Apple "
        "TV+. The rest of the folder name becomes its own category (Kids, Christmas, Asia), "
        "which you can browse across every service, and 4K is recorded as the picture quality.",
        "\"MULTI\" in a folder name now marks titles with several audio or subtitle languages, "
        "the same as \"(MULTI SUB)\" in a title, instead of being part of the folder's name.",
    ),
    test_steps=(
        "Wait for the channel update to finish in the migration progress area after launch.",
        "Open the Platform filter and choose Netflix: titles from folders such as Netflix Kids "
        "and Netflix Christmas are included.",
        "Choose Amazon Prime: the count is much larger than before and includes 4K folders.",
        "Open a title from a \"|MULTI| NETFLIX KIDS\" folder: it shows Netflix, Kids and "
        "multiple languages, and no \"Multi Netflix Kids\" collection.",
    ),
)
