from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=7,
    version="1.0.1",
    date="2026-11-11",
    title="RAW in folder names counts as quality; VIP is no longer a platform",
    items=(
        "Small raised letters in a source's folder names, such as \"ᴿᴬᵂ\" in "
        "\"TELE2 VERMAAK ᴿᴬᵂ ᴳᴼᴸᴰ\", are now read the same way as in channel names: RAW counts "
        "as the picture quality, and the marks no longer appear in collection names.",
        "\"VIP\" and \"GOLD\" in folder names mark a package level, not a streaming service, so "
        "they no longer appear as platforms. A folder like \"LAT| MEXICO VIP\" now counts only "
        "as Mexico and Latin American Spanish.",
        "Folders named \"DISNEY +\" (with a space) and \"DISNEYTV+\" now count as Disney+.",
    ),
    test_steps=(
        "Wait for the channel update to finish in the migration progress area after launch.",
        "Open the Platform filter: there is no VIP or GOLD entry.",
        "Open the Quality filter and choose RAW: channels from folders marked \"ᴿᴬᵂ\" are "
        "included.",
        "Open a channel from a \"LAT| MEXICO VIP\" folder: it shows Mexico and Spanish, and no "
        "VIP platform.",
        "Choose Disney+ in the Platform filter: titles from \"DISNEY +\" and \"DISNEYTV+\" "
        "folders are included.",
    ),
)
