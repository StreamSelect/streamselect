from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=139,
    version="1.5.0",
    date="2026-11-28",
    title="Right-click a Discover row or tile for its actions, including delete",
    items=(
        "Right-click a row's name (or an empty part of the row) or a tile: Expand or Collapse, "
        "Pin to top or Unpin, See all, and Hide this shelf.",
        "On a list you made (Watch Later and your other categories), \"Delete list…\" removes "
        "the list after asking; the titles in it stay in your library.",
        "On a saved recipe, \"Edit recipe…\" opens it in Recipe and \"Delete recipe…\" deletes "
        "it after asking.",
    ),
    test_steps=(
        "Right-click the Horror tile: Expand Horror, Pin to top, See all, Hide this shelf. "
        "No delete.",
        "Make a test list (right-click a title ▸ category ▸ new), then right-click its tile in "
        "Discover ▸ Delete list…: a question asks first; Yes: the shelf goes, the status bar "
        "says how many titles were kept, and the titles are still in your library.",
        "Right-click a saved recipe's shelf ▸ Delete recipe… ▸ Yes: it leaves Discover and "
        "Recipe's Saved tab.",
    ),
)
