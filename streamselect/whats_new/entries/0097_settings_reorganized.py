from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=97,
    version="1.2.0",
    date="2026-11-22",
    title="Settings: grouped sections, every setting explained, and Find",
    items=(
        "The Settings list is grouped under headings: Watching, Finding things, Alerts, and "
        "App & data.",
        "The right-hand column now explains every setting on the page, not just the page as "
        "a whole. Click a setting's name, or move into its value, and the column jumps to "
        "its explanation while the row is tinted. Click a name in the column to scroll the "
        "page to that setting.",
        "\"Find a setting…\" above the list keeps only the sections whose settings match "
        "what you type, with a count for each, and tints the matching rows. A match inside "
        "Sports' collapsed Advanced box opens it.",
        "The \"Still watching?\" question after an autoplayed run has a link that opens "
        "Settings at the option that turns it off.",
        "Drop-down lists and number boxes are sized to their values on every page; text "
        "fields still use the full width.",
        "Signal checking's \"Hide after\" now says what it counts (\"2 checks\").",
    ),
    test_steps=(
        "Open Settings: sections sit under four headings; the Down arrow steps from the last "
        "section under Watching to Content without stopping on a heading.",
        "On Playback, click the \"Buffering:\" label: the right column shows Buffering's "
        "explanation at the top and the Buffering row is tinted.",
        "Tab into \"Video decoder\": the column jumps to Video decoder.",
        "In the column, click a setting near the bottom of the page: the page scrolls to "
        "that row.",
        "Type \"refresh\" in Find a setting: only sections with a match stay, each with a "
        "count; clear it and every section comes back.",
        "Type \"clock evidence\": Settings switches to Sports and opens its Advanced box at "
        "that row.",
        "Play a season with autoplay so it advances at least once, close the player, and "
        "click \"Change whether this is asked\" on the question: Settings opens on Playback "
        "with the \"Ask 'Still here?'\" row tinted.",
        "On Signal checking, the number boxes are narrow, and \"Hide after\" reads "
        "\"2 checks\".",
    ),
)
