from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=129,
    version="1.4.0",
    date="2026-11-27",
    title="No crash when Discover reloads while posters download",
    items=(
        "The app could close suddenly when Discover rebuilt its rows (a reload, a source "
        "change, a new card size) while posters were still downloading. A poster for a row "
        "that's gone is now simply dropped.",
    ),
    test_steps=(
        "Open Discover with several rows open, and straight away drag the card-size slider a "
        "few times, or click \"Live categories\" twice, while the posters are still loading: "
        "the app stays open and the rebuilt rows fill in their posters.",
    ),
)
