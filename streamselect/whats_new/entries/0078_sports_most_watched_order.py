from streamselect.whats_new import WhatsNewEntry

ENTRY = WhatsNewEntry(
    id=78,
    version="1.0.7",
    date="2026-11-18",
    title="Sports: the leagues you watch most come first",
    items=(
        "Sports now orders its sports and leagues by how many days you watched them in the "
        "last 30, with total time watched breaking ties. Leagues you haven't watched follow "
        "in A–Z order.",
        "A game counts toward its league when the channel's name says the league, or when it "
        "names two of that league's teams, so a game on a channel that never says \"NHL\" "
        "still counts as NHL.",
        "The \"Most watched\" button in the toolbar switches to plain A–Z order and back.",
    ),
    test_steps=(
        "Watch a game in one league (e.g. NHL) for a few minutes, then wait for the next games "
        "refresh or restart the app. Open Sports with \"Less certain games\" on and several "
        "leagues listed: the league you watched is the first league heading, and its chip is "
        "first in the sport's header.",
        "Click \"Most watched\" in the toolbar: it reads \"A–Z\" and the leagues are in "
        "alphabetical order. Click again to go back. Restart the app: your choice is kept.",
    ),
)
