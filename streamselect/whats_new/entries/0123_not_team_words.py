from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=123,
    version="1.3.1",
    date="2026-11-27",
    title="Fewer made-up teams",
    items=(
        "Words that are never part of a team's name are left out when a listing's two sides "
        "are read: \"NBA herrar New York Knicks\" is the New York Knicks, a \"Matchday\" show "
        "with its broadcaster is not a game, and \"UK Basketball\" is UK. Teams already kept "
        "under such a name are removed at the next Sports refresh.",
    ),
    test_steps=(
        "Start the app and wait for the Sports view to find today's games.",
        "Tools ▸ Library Breakdown ▸ Sports ▸ Basketball ▸ NBA: \"New York Knicks\" is listed "
        "and \"Herrar New York Knicks\" is not.",
        "Hockey ▸ NHL: \"Matchday\" is not listed as a team.",
    ),
)
