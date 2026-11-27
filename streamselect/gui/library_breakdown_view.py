"""Tools ▸ Library breakdown: how the app sorted your channels, and what it couldn't sort.

Design "Library Breakdown" rev 1 (owner accepted BV-Q1-Q13, 2026-11-27). A
read-only Tools view (BV-Q1) with one tab per grouping (BV-Q2), built from the
Analytics tab's parts (``gui/analytics_parts.py``, BV-Q3):

* **Sports** — figure tiles for the kinds; every sport with channels and how
  each was decided (``sport_from``, BV-Q5); clicking a sport lists its leagues
  and what the game finder does with each (BV-Q8); clicking a league lists its
  teams, confirmed first and the names only listings gave below (BV-Q7). The
  view opens on the first sport in the Sports view's order (BV-Q6).
* **Nothing identified** — the catch-all (One Sports List slice 6): games two
  leagues fit, games between teams no list knows by collection (BV-Q12), and
  listings that aren't games (BV-Q9).

A name selects; a count (or a tile) opens those channels in Search through the
host's strict context filter (BV-Q4). Both reads run off the UI thread through
the host's ``_run_query`` seam; the data is ``core/library_breakdown.py``'s.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QScrollArea, QTabWidget, QVBoxLayout, QWidget

from streamselect.core import library_breakdown as lb
from streamselect.core import sports_catalog as sc
from streamselect.gui import cursor_affordance
from streamselect.gui.analytics_parts import AnalyticsCard, FigureTile, LinkLabel, short_bar, text_label
from streamselect.gui.chip_row import MiddleElideLabel
from streamselect.gui.tool_view import ToolView, clear_layout, show_loading, show_panel_error

#: What the game finder does with a league (BV-Q8).
FINDER_WORDS = {sc.FINDER_LISTED: "finds games", sc.FINDER_TRIAL: "finds games (trial)",
                sc.FINDER_OFF: "tags only", "": "not in the list"}
#: Rows shown before a card's Show all.
SPORT_ROWS, LEAGUE_ROWS, COLLECTION_ROWS, NOT_GAME_ROWS = 12, 8, 16, 8
#: Team names per row, and unconfirmed names shown before Show all (two rows, BV-Q7).
TEAMS_ACROSS, UNCONFIRMED_SHOWN = 3, 6


class _Tile(FigureTile):
    """A figure tile that opens its channels when clicked (BV-Q4)."""

    clicked = pyqtSignal()

    def __init__(self, tooltip: str) -> None:
        super().__init__()
        self.setToolTip(tooltip)
        cursor_affordance.set_clickable(self)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 — Qt override
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


def _scrolled(body: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setWidget(body)
    return area


class LibraryBreakdownView(ToolView):
    """The view. ``on_activate`` (re)loads both tabs."""

    #: (label, channel ids): the host opens them in Search as a strict filter.
    browse_requested = pyqtSignal(str, object)

    def __init__(self, main_window) -> None:
        super().__init__(main_window)
        self._tokens = {k: [0] for k in ("sports", "catch", "browse")}
        self._sports: lb.SportsBreakdown | None = None
        self._sport = ""
        self._league: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.addLayout(self.build_top_bar("Library breakdown"))
        layout.addWidget(text_label("How the app sorted your channels, and what it couldn't sort. "
                                    "Counts are of your enabled sources.", "META_HINT"))
        self.tabs = QTabWidget()
        self._sports_body = QVBoxLayout()
        self._catch_body = QVBoxLayout()
        for body, title, tip in ((self._sports_body, "Sports", "Every sport and how it was decided"),
                                 (self._catch_body, "Nothing identified",
                                  "Sports listings no rule identified, grouped by what would fix them")):
            page = QWidget()
            page.setLayout(body)
            body.setContentsMargins(0, 8, 0, 0)
            body.setSpacing(10)
            self.tabs.addTab(_scrolled(page), title)
            self.tabs.setTabToolTip(self.tabs.count() - 1, tip)
        layout.addWidget(self.tabs, 1)

    # ── loading ──────────────────────────────────────────────────────────

    def on_activate(self) -> None:
        run = self.main_window._run_query
        show_loading(self._sports_body)
        show_loading(self._catch_body)
        run(lambda repos: lb.sports_breakdown(repos.session), self._on_sports,
            token_ref=self._tokens["sports"], on_error=lambda e: show_panel_error(self._sports_body, e))
        run(lambda repos: lb.catch_all(repos.session), self._on_catch,
            token_ref=self._tokens["catch"], on_error=lambda e: show_panel_error(self._catch_body, e))

    def on_deactivate(self) -> None:
        for token in self._tokens.values():   # a result arriving after we left is dropped
            token[0] += 1

    def _browse(self, label: str, **where) -> None:
        self.main_window._run_query(lambda repos: lb.channel_ids(repos.session, **where),
                                    lambda ids: self.browse_requested.emit(label, ids),
                                    token_ref=self._tokens["browse"])

    def _tile(self, row: QHBoxLayout, figure: int, caption: str, label: str, *, warn: bool = False,
              **where) -> None:
        tile = _Tile(f"Show these {figure:,} channels in Search")
        tile.set(f"{figure:,}", caption, warn=warn)
        tile.clicked.connect(lambda: self._browse(label, **where))
        row.addWidget(tile, 1)

    def _count(self, n: int, label: str, **where) -> LinkLabel:
        link = LinkLabel(f"{n:,}", f"Show these {n:,} channels in Search")
        link.clicked.connect(lambda: self._browse(label, **where))
        return link

    # ── Sports tab ───────────────────────────────────────────────────────

    def _on_sports(self, data: lb.SportsBreakdown) -> None:
        self._sports = data
        self._sport = data.first_sport
        self._league = self._first_league(self._sport)
        self._render_sports()

    def _first_league(self, sport: str) -> str | None:
        rows = self._sports.leagues.get(sport, ()) if self._sports else ()
        return next((r.name for r in rows if r.confirmed or r.unconfirmed), None)

    def _select(self, sport: str | None = None, league: str | None = None) -> None:
        if sport is not None:
            self._sport, self._league = sport, self._first_league(sport)
        if league is not None:
            self._league = league
        self._render_sports()

    def _render_sports(self) -> None:
        data = self._sports
        clear_layout(self._sports_body)
        k = data.kinds
        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        for figure, caption, where, warn in (
                (data.total, "sports, PPV and event channels", {}, False),
                (k.get(lb.SPORT, 0), "say their sport", {"kind": lb.SPORT}, False),
                (k.get(sc.NETWORK, 0), "many-sports channels", {"kind": sc.NETWORK}, False),
                (k.get(sc.SLOT, 0), "event slots", {"kind": sc.SLOT}, False),
                (k.get(sc.UNKNOWN, 0), "nothing identified", {"kind": sc.UNKNOWN}, True),
                (k.get(lb.NONE, 0), "events that aren't sports", {"kind": lb.NONE}, False)):
            self._tile(tiles, figure, caption, caption.capitalize(), warn=warn and figure > 0, **where)
        self._sports_body.addLayout(tiles)
        cols = QHBoxLayout()
        cols.setSpacing(10)
        cols.addWidget(self._sports_card(data), 5)
        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(self._leagues_card(data))
        right.addWidget(self._teams_card(data))
        right.addStretch(1)
        cols.addLayout(right, 4)
        self._sports_body.addLayout(cols)
        self._sports_body.addStretch(1)

    def _sports_card(self, data: lb.SportsBreakdown) -> AnalyticsCard:
        card = AnalyticsCard("Sports")
        card.subtitle.setText(f"{len(data.sports)} sports")
        if not data.sports:
            card.text("No channel says its sport yet.")
            return card
        grid = card.grid()
        grid.setColumnStretch(3, 1)
        for col, head in ((1, "Channels"), (3, "Decided by")):
            grid.addWidget(text_label(head, "META_HINT"), 0, col)
        named = max(1, data.kinds.get(lb.SPORT, 0))
        hidden = []
        for row, s in enumerate(data.sports, start=1):
            if s.key == self._sport:
                name = text_label(s.name, "FIELD_LABEL")
            else:
                name = LinkLabel(s.name, f"Show {s.name}'s leagues and teams")
                name.clicked.connect(lambda key=s.key: self._select(sport=key))
            how = " · ".join(f"{sc.FROM_WORDS.get(f, f or 'not recorded')} {n / s.channels:.0%}"
                             for f, n in s.decided_by)
            cells = (name, self._count(s.channels, s.name, sport=s.key), short_bar(s.channels / named),
                     text_label(how, "META_HINT"))
            for col, widget in enumerate(cells):
                grid.addWidget(widget, row, col)
            if row > SPORT_ROWS:
                hidden.extend(cells)
        card.show_all(hidden, len(data.sports))
        card.layout().addStretch(1)
        return card

    def _leagues_card(self, data: lb.SportsBreakdown) -> AnalyticsCard:
        name = sc.sport_label(self._sport)
        rows = data.leagues.get(self._sport, ())
        card = AnalyticsCard(f"{name} · leagues")
        card.subtitle.setText(f"{sum(1 for r in rows if r.name)} leagues")
        grid = card.grid()
        grid.setColumnStretch(3, 1)
        for col, head in enumerate(("League", "Channels", "Teams", "Game finder")):
            grid.addWidget(text_label(head, "META_HINT"), 0, col)
        hidden = []
        for row, r in enumerate(rows, start=1):
            title = r.name or "no league named"
            if r.name and r.name == self._league:
                label = text_label(title, "FIELD_LABEL")
            elif r.name:
                label = LinkLabel(title, f"Show the {title} teams")
                label.clicked.connect(lambda n=r.name: self._select(league=n))
            else:
                label = text_label(title, "META_HINT")
            teams = (f"{r.confirmed} confirmed · {r.unconfirmed} unconfirmed"
                     if r.confirmed or r.unconfirmed else "—")
            cells = (label, self._count(r.channels, f"{name} · {title}", sport=self._sport, league=r.name),
                     text_label(teams, "META_HINT"), text_label(FINDER_WORDS.get(r.finder, r.finder), "META_HINT"))
            for col, widget in enumerate(cells):
                grid.addWidget(widget, row, col)
            if row > LEAGUE_ROWS:
                hidden.extend(cells)
        card.show_all(hidden, len(rows))
        return card

    def _teams_card(self, data: lb.SportsBreakdown) -> AnalyticsCard:
        league = self._league
        teams = data.teams.get(f"{self._sport}/{league}", ()) if league else ()
        card = AnalyticsCard(f"{league} · teams" if league else "Teams")
        if not teams:
            card.text("The game finder has learned no teams for this sport yet."
                      if not league else "No teams learned for this league yet.", "META_HINT")
            return card
        confirmed = [n for n, c in teams if c]
        unconfirmed = [n for n, c in teams if not c]
        card.subtitle.setText(f"{len(confirmed)} confirmed · {len(unconfirmed)} unconfirmed")
        grid = card.grid()
        for i, n in enumerate(confirmed):
            grid.addWidget(text_label(n, "FIELD_LABEL"), *divmod(i, TEAMS_ACROSS))
        if unconfirmed:
            card.text("Unconfirmed: named in listings, no game found yet", "META_HINT")
            grid = card.grid()
            hidden = []
            for i, n in enumerate(unconfirmed):
                label = text_label(n, "META_HINT")
                grid.addWidget(label, *divmod(i, TEAMS_ACROSS))
                if i >= UNCONFIRMED_SHOWN:
                    hidden.append(label)
            card.show_all(hidden, len(unconfirmed))
        return card

    # ── Nothing identified tab ───────────────────────────────────────────

    def _on_catch(self, data: lb.CatchAll) -> None:
        clear_layout(self._catch_body)
        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        self._tile(tiles, data.total, "sports listings nothing identified", "Nothing identified",
                   warn=data.total > 0, kind=sc.UNKNOWN)
        for figure, caption in ((len(data.either), "could be either of two leagues"),
                                (data.strangers_total, "games between teams no list knows"),
                                (len(data.not_games), "not a game")):
            tile = FigureTile()
            tile.set(f"{figure:,}", caption)
            tiles.addWidget(tile, 1)
        if data.named_by_teams:
            tile = FigureTile()
            tile.set(f"{data.named_by_teams:,}", "named by their teams at the next game-finder run")
            tiles.addWidget(tile, 1)
        self._catch_body.addLayout(tiles)
        cols = QHBoxLayout()
        cols.setSpacing(10)
        left = QVBoxLayout()
        left.setSpacing(10)
        left.addWidget(self._either_card(data))
        left.addWidget(self._not_games_card(data))
        left.addStretch(1)
        cols.addLayout(left, 4)
        cols.addWidget(self._strangers_card(data), 5)
        self._catch_body.addLayout(cols)
        self._catch_body.addStretch(1)

    def _either_card(self, data: lb.CatchAll) -> AnalyticsCard:
        card = AnalyticsCard("Could be either")
        card.subtitle.setText("two leagues")
        if not data.either:
            card.text("No listing fits two leagues.", "META_HINT")
            return card
        grid = card.grid()
        grid.setColumnStretch(0, 1)
        for row, (name, leagues) in enumerate(data.either):
            grid.addWidget(MiddleElideLabel(name, color_token="COLOR_TEXT"), row, 0)
            grid.addWidget(text_label(" or ".join(leagues), "META_HINT"), row, 1)
        return card

    def _not_games_card(self, data: lb.CatchAll) -> AnalyticsCard:
        card = AnalyticsCard("Not a game")
        card.subtitle.setText("no matchup")
        if not data.not_games:
            card.text("Every listing here names a matchup.", "META_HINT")
            return card
        grid = card.grid()
        hidden = []
        for row, name in enumerate(data.not_games):
            label = MiddleElideLabel(name, color_token="COLOR_TEXT")
            label.setToolTip(name)
            grid.addWidget(label, row, 0)
            if row >= NOT_GAME_ROWS:
                hidden.append(label)
        card.show_all(hidden, len(data.not_games))
        return card

    def _strangers_card(self, data: lb.CatchAll) -> AnalyticsCard:
        card = AnalyticsCard("Games between teams no list knows")
        card.subtitle.setText(f"{len(data.strangers)} collections")
        if not data.strangers:
            card.text("None.", "META_HINT")
            return card
        grid = card.grid()
        grid.setColumnStretch(2, 1)
        for col, head in enumerate(("Collection", "Games", "For example")):
            grid.addWidget(text_label(head, "META_HINT"), 0, col)
        hidden = []
        for row, g in enumerate(data.strangers, start=1):
            title = g.collection or "no collection"
            example = MiddleElideLabel(" · ".join(g.examples), color_token="COLOR_TEXT")
            example.setToolTip("\n".join(g.examples))
            cells = (text_label(title, "FIELD_LABEL"),
                     self._count(g.games, f"Unidentified in {title}", collection=g.collection), example)
            for col, widget in enumerate(cells):
                grid.addWidget(widget, row, col)
            if row > COLLECTION_ROWS:
                hidden.extend(cells)
        card.show_all(hidden, len(data.strangers))
        card.layout().addStretch(1)
        return card
