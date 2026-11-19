from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=94,
    version="1.2.0",
    date="2026-11-19",
    title="The cast and crew tip points at the right place",
    items=(
        "The first-time tip about cast and crew now outlines the whole Cast section, "
        "directors and cast together, instead of a single name.",
        "Tips and the tour keep their outline on the control if the window rearranges "
        "while the tip is open, instead of staying on the empty space it left.",
    ),
    test_steps=(
        "Tools ▸ Show tips again, then select a film with cast in the details pane and "
        "dismiss the rating tip: on the next title the Cast tip outlines the whole Cast "
        "section, header, Directed by and cast names included.",
        "Select a title whose details are still loading (stream details arrive late): the "
        "outline moves with the Cast section rather than staying where it first was.",
    ),
)
