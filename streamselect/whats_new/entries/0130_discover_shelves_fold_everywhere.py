from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=130,
    version="1.5.0",
    date="2026-11-27",
    title="Discover: every section folds, and Manage changes show at once",
    items=(
        "\"Your lists\" is now \"Your Shelves\". It and \"Discover's Shelves\" fold from their "
        "heading like Genres, Decades and Provider Categories, each showing how many rows it "
        "holds; Pinned stays open.",
        "Collapsing, opening, pinning or hiding rows in Manage now changes just those rows "
        "when you close it, instead of reloading the whole page. Before, a change made while "
        "Discover was still loading could be lost, so a row you collapsed stayed open.",
        "Opening several rows at once (Manage's Expand all, for example) fills every one of "
        "them; only the last one used to fill.",
    ),
    test_steps=(
        "Open Discover: the second section is \"Your Shelves (N)\". Click its heading: Watch "
        "Later, Recommended and Watch Queue fold away; click again to bring them back. Do the "
        "same with \"Discover's Shelves\". Restart: each heading is as you left it.",
        "Collapse Watch Later with its own arrow: it becomes a single row in place. Restart: "
        "still collapsed.",
        "Manage: collapse Watch Later, open a genre, move a pinned row down, then Close. Only "
        "those rows change; the page doesn't go back to \"Loading…\".",
        "Manage: Expand all, Close: each row fills with posters in turn.",
        "Open Manage straight after opening Discover, while it is still loading: changes still "
        "take effect.",
    ),
)
