from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=8,
    version="1.0.1",
    date="2026-11-11",
    title="More channel name prefixes recognised",
    items=(
        "Tamil channels marked \"TM\" were listed as Russian. They now count as Tamil (Indian "
        "languages).",
        "Premium 24/7 channels such as \"PB-PREM\" or \"IN-PREM\" had no language or country. "
        "They now get the one the prefix names: Punjabi, India, Pakistan, Tamil or Kannada. "
        "The same applies to other combined prefixes such as \"AR-4K\" or \"IN-EN\".",
        "Prefixes naming a TV operator's channel package, such as Tele2 (\"T2\"), Cabel TV, "
        "Avatel, NOS, Caiway, Direct One, Vision+, Viaplay and BBC iPlayer, now count under "
        "Pay TV or Other Streaming.",
        "\"FRQ\" and \"CA-FR\" count as Quebec French, and \"KURD\", \"SRB\", \"SKR\", \"MH\", "
        "\"BANGLA\", \"ZIMBABWE\" and \"SU\" as Kurdish, Serbia, South Korea, Marathi, Bengali, "
        "Zimbabwe and Suriname.",
    ),
    test_steps=(
        "Wait for the channel update to finish in the migration progress area after launch.",
        "Open a channel from an \"IN| TAMIL MOVIES\" folder: it shows an Indian language, not "
        "Russian.",
        "Open a \"PB-PREM\" channel: it shows an Indian language.",
        "Open a \"T2\" channel: its platform shows Pay TV and its region the Netherlands.",
        "Open an \"FRQ\" title: it shows Quebec French.",
    ),
)
