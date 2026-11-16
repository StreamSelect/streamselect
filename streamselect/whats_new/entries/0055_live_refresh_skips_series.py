from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=55,
    version="1.0.5",
    date="2026-11-16",
    title="Live-channel refreshes no longer re-check every series",
    items=(
        "The scheduled live-channel refresh used to check every series you monitor for "
        "new episodes, one request to your source each, though it can't change any "
        "series. Now only a full catalog refresh checks series and movie Watch Alerts, "
        "so an app left open makes far fewer requests.",
    ),
    test_steps=(
        "With live refresh set to 15 minutes and a few monitored series, leave the app "
        "open past one live refresh: the log shows the live channels reloading and no "
        "\"fetch_series_info\" lines after it.",
        "Refresh a source fully (its Refresh button): monitored series are checked "
        "afterwards, and new episodes still raise their alert.",
    ),
)
