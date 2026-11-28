from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=142,
    version="1.5.0",
    date="2026-11-28",
    title="Discover cards show your rating and add to Watch Later in one click",
    items=(
        "A card shows how you judged the title: liked, disliked or not interested, so you can "
        "see at a glance what you've already decided on. It counts for every copy of the "
        "title, whichever source you rated it under.",
        "Hover a poster in Discover for a Watch Later button in its corner; click it to add the "
        "title. A title already in Watch Later shows the button all the time; click it to "
        "take the title out.",
    ),
    test_steps=(
        "Like one title and dislike another (details pane), then open Discover: their cards "
        "show the like and dislike icons in the top-right corner. Mark a title Not "
        "Interested: its card shows that icon.",
        "Hover a poster in an open row: a bookmark button appears top-right. Click it: the "
        "title joins the Watch Queue (sidebar) and the bookmark stays. Click it again: it "
        "leaves the queue.",
        "Same in a row's See all grid.",
    ),
)
