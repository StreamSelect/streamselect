from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=21,
    version="1.0.1",
    date="2026-11-12",
    title="One-time tips for each view, rating and cast, and tooltips on every button",
    items=(
        "The first time you open EPG, Recommended, Discover or Recipe, a short tip says "
        "what that view is for.",
        "The first time a title's details appear, a tip explains like, not interested "
        "and dislike: like a few things you already enjoy and Recommended starts "
        "finding more. A later title explains that clicking a cast or crew name lists "
        "everything they're in.",
        "Tools ▸ Show tips again brings every tip back, to show at its next moment.",
        "Buttons that had no tooltip now explain themselves when you hover over them, "
        "including Add Source, EPG's filter buttons, Show All, Cancel and Back.",
    ),
    test_steps=(
        "Choose Tools ▸ Show tips again, then click Discover: a tip rings the Discover "
        "button and says what the view is for. Click Discover again later: no tip.",
        "Click a film in Search: once its details load, a tip rings the like, not "
        "interested and dislike buttons. Click another title: a tip rings a cast name.",
        "Open EPG and hover over the Category and All Types buttons and Show All: each "
        "shows a tooltip.",
    ),
)
