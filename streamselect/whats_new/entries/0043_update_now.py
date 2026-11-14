from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=43,
    version="1.0.4",
    date="2026-11-14",
    title="Updates install themselves on Mac and Windows",
    items=(
        "When a new version is out, a notice names it and stays until you answer: Now, Later, "
        "Skip or Never. Skip passes over that version; Never stops the automatic check.",
        "On a Mac or Windows PC, Now downloads the update, replaces the app and starts the new "
        "version. If the app can't replace itself (for example, it is in a folder you can't "
        "change), Now falls back to the download.",
        "On Linux the notice works the same way, and Now opens the download page.",
        "Tools ▸ Software Update… checks right away, and Tools ▸ Check for Updates "
        "Automatically turns the daily check on or off.",
    ),
    test_steps=(
        "Open the Tools menu: it has Software Update… and a ticked Check for Updates "
        "Automatically.",
        "Choose Software Update…: on the newest version it says you're up to date.",
        "Start a packaged build with STREAMSELECT_UPDATE_FORCE=1 and choose Software Update…: "
        "a notice offers the latest release with Now, Later, Skip and Never, and has no close "
        "button.",
        "Choose Never: the notice closes, a message says automatic checks are off, and the "
        "Tools menu's Check for Updates Automatically is now unticked. Tick it again.",
        "On a Mac or Windows build in a folder you can write to, force the notice again and "
        "choose Now: a progress notice counts up, the app closes, and the installed version "
        "starts by itself.",
    ),
)
