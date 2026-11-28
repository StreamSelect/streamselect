from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=128,
    version="1.4.0",
    date="2026-11-27",
    title="Discover as your dashboard",
    items=(
        "Discover reads top to bottom in groups: what you pinned, your lists, Discover's own "
        "rows (Recently Added, Top Rated, the featured actor, streaming services), every "
        "genre, the years and decades, then the provider's categories.",
        "Your lists open at the top: Watch Later, Recommended for You (once it has something to "
        "suggest) and your Watch Queue, a new row with your queue's films and series in queue "
        "order. A queued episode shows as its series.",
        "This decade is listed a year at a time (2026, 2025 … 2020); earlier ones by decade.",
        "Genres, Decades and Provider Categories each fold from their heading, which shows how "
        "many rows they hold, and stay as you left them.",
        "Opening or collapsing a row leaves it where it is. Pin a row (any genre, year or "
        "category) to bring it to the top; unpin it and it goes back to its place.",
        "Category rows now show their region chips (they were missing in the previous build).",
    ),
    test_steps=(
        "Open Discover: Pinned (if you pinned any), then Your lists with Watch Later, "
        "Recommended for You and Watch Queue open, then Discover's rows, Genres, Decades, "
        "Provider Categories.",
        "Watch Queue shows your queued films and series in the sidebar queue's order; a queued "
        "episode appears once, as its series; live channels are not there.",
        "Decades: 2026 down to 2020 one by one, then 2010s and older. Open 2025: its titles "
        "are from 2025.",
        "Click the Genres heading: its rows fold away and the page closes up; the count is in "
        "the heading. Restart: still folded. Click again to unfold.",
        "Expand a genre: it opens where it is. Pin it: it moves to the top. Unpin: back in "
        "Genres at the same place.",
        "Provider Categories: a category row shows region chips after its name.",
    ),
)
