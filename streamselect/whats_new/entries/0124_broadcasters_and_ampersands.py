from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=124,
    version="1.3.1",
    date="2026-11-27",
    title="Texas A&M, and broadcasters that are not teams",
    items=(
        "A team name with \"&\" keeps it: Texas A&M is no longer split into \"Ta M\" or "
        "shortened to \"E Texas\".",
        "A broadcaster or a presenter credit is never a team: \"… with Sky Sport\" and a Hong "
        "Kong guide title \"M1 Group - Sports to the World presents …\" are no longer read as "
        "games. Teams already kept under a name the app now reads differently are removed at "
        "the next Sports refresh.",
    ),
    test_steps=(
        "Start the app and wait for the Sports view to find today's games.",
        "Tools ▸ Library Breakdown ▸ Sports ▸ Basketball ▸ NCAAB: a team reads \"A&M\" with "
        "its ampersand (e.g. \"E Texas A&M\"), not \"E Texas Am\".",
        "Hockey ▸ NHL: \"Mit Sky Sport\" is not listed as a team; Basketball ▸ FIBA: \"Sports To "
        "The World\" is not listed.",
    ),
)
