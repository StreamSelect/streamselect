from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=5,
    version="1.0.1",
    date="2026-11-11",
    title="Channels in continent folders get their real country",
    items=(
        "Some sources group channels by continent first, as in \"AM| CANADA HD\" or "
        "\"AM| BRAZIL\". AM was read as Armenia, so Canadian, Brazilian, Latin American and "
        "other channels in that folder were listed as Armenian. StreamSelect now recognises a "
        "continent folder by the many countries filed under it, and uses the country inside "
        "it instead.",
        "\"NA\" now means North America instead of Namibia. Channels such as North American "
        "hockey teams and the North American feeds of foreign channels (marked \"(NA)\") "
        "were listed under Namibia and as English.",
    ),
    test_steps=(
        "Wait for the channel update to finish in the migration progress area after launch.",
        "In the filter panel, open Region: Armenia lists only Armenian channels, not Canadian "
        "or Brazilian ones.",
        "Search for a Canadian channel from a continent folder (e.g. CTV): its details show "
        "Canada, with no Armenian language.",
        "In the filter panel, Namibia is gone or nearly empty, and North America appears; a "
        "channel marked \"(NA)\" shows North America.",
    ),
)
