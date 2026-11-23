from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=102,
    version="1.2.0",
    date="2026-11-22",
    title="Sports remembers a channel you reported, after the report stops counting",
    items=(
        "Sports: a channel you reported \"Nothing showing\" is no longer forgotten once the "
        "report stops counting (30 days for each report). It keeps its flag with "
        "\"· reported <date>\" and is listed below every channel never reported, above any "
        "reported now. If it is your PREFERRED channel it stays first.",
        "Watching it for real (Settings → Sports \"Watching takes a report back after\") "
        "forgets it, and so does \"Forget reports\" in its right-click menu (it was \"Clear "
        "bad reports\"). Reporting it again counts the old reports too, so it stays down "
        "longer each time. \"Not this game\" is about one game and is not remembered.",
    ),
    test_steps=(
        "In Sports, open a game's channel list and pick a channel you reported \"Nothing "
        "showing\" more than 30 days ago (or ask a developer to backdate one): it has the "
        "flag, \"· reported <date>\" after its name, and sits below the channels never "
        "reported. Hover the flag: \"Reported before (nothing showing), last on <date>…\".",
        "Right-click that channel: a greyed \"Reported before: nothing showing, last on "
        "<date>\" line sits above the two reports; \"Forget reports\" is enabled. Choose it: "
        "the flag and date go and the channel returns to its usual place.",
        "Report a channel \"Nothing showing\" now: it has the flag without a date and is "
        "listed last, below the one reported before.",
        "Make the channel reported before your PREFERRED one: it moves to the top.",
    ),
)
