from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=134,
    version="1.5.0",
    date="2026-11-28",
    title="Year and decade rows open instantly",
    items=(
        "Opening a year or decade row in Discover (2025, the 1990s…) took about 30 seconds on "
        "a large library; it now takes a moment. Each title's release year is stored when its "
        "details arrive instead of being looked up across the whole library every time.",
        "Discover also works out which years and decades to list faster when it opens.",
        "The first launch after updating reads the release year of the titles you already "
        "have (about a minute on a large library; shown in Migration Center).",
    ),
    test_steps=(
        "Launch once and let \"Reading details the provider already sent\" finish in Tools ▸ "
        "Migration Center.",
        "Discover ▸ Decades: expand 2025: its posters appear almost at once, all from 2025. "
        "Expand the 1990s: same, all from 1990–1999.",
        "The Decades heading lists the same years and decades as before.",
    ),
)
