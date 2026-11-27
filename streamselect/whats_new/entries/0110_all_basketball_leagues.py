from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=110,
    version="1.3.0",
    date="2026-11-23",
    title="Sports: every major basketball league, not just the NBA",
    items=(
        "Sports now also looks for basketball games in men's and women's college basketball "
        "(NCAAB, NCAAW), the WNBA, the G League, the EuroLeague and EuroCup, FIBA "
        "competitions, the Basketball Champions League, and the top leagues of Spain (ACB), "
        "Italy (LBA), Germany (BBL), France (LNB), Greece, Turkey, the Adriatic (ABA), "
        "Russia (VTB), Australia (NBL), China (CBA), Japan, Korea, the Philippines, Mexico, "
        "Brazil and Africa, plus BIG3. Each shows under its short name. They are on trial "
        "while their results are checked.",
        "A league that no channel, guide programme or recent play mentions is skipped when "
        "games are looked for, so the extra leagues don't slow the search.",
    ),
    test_steps=(
        "On an evening with college basketball, open Sports ▸ Basketball: NCAAB has its own "
        "heading beside NBA, with games such as two colleges' names.",
        "If women's college games are on, NCAAW has its own heading and its games are not "
        "also listed under NCAAB.",
        "On a Tuesday or Thursday, the EuroLeague's games show under EuroLeague.",
    ),
)
