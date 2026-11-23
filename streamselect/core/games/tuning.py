"""Each sport's game timings: predefined defaults, the user's own choices, and
which defaults improved since the user chose (Settings ▸ Sports; design "Sports
Settings" rev 1, SS-Q1–Q11, owner 2026-11-18).

Owner: "we should not be hardcoding ANYTHING in the app with regards to the user
experience like length of sporting events … predefined but flexible."

- Defaults live in the bundled ``sports_definitions.yaml`` under ``sport_defaults``:
  ``default`` holds every value; a sport's own block overrides only what differs.
- A user's choices are stored apart (``Config.sport_settings_overrides``), as
  ``{sport: {key: [value, default_when_chosen]}}``. Only values the user SET are
  stored — a value set equal to the default is still the user's choice (owner:
  setting it back to an old default must not be moved by the next update). Reset
  deletes the entry, and the setting follows the defaults again.
- ``improved()`` lists stored choices whose default has moved since: the
  "Some defaults were improved" prompt asks keep-mine or take-new, once.
- **All sports** (owner, 2026-11-18): the user's choices under :data:`ALL` apply to
  every sport that sets none of its own. A value comes from the most specific
  place that sets it: the user's for the sport, the user's for All sports, the
  sport's shipped default, the shipped default. Each setting says where it may be
  set (:attr:`Spec.scope`): game length only per sport; "Most watched" and the
  clock settings only for all sports (they rank sports against each other, and a
  clock belongs to a collection, which carries many sports); the rest at both.

Values are whole numbers in the unit the Settings page shows (minutes, hours,
days, seconds); :func:`settings_kwargs` turns them into ``SportSettings`` fields.
No Qt and no ``Config`` here: callers pass the overrides mapping in.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from typing import Mapping, Optional

import yaml

from streamselect.core.special_content import _BUNDLED_DEFINITIONS

GAME, LISTED, ALERTS, WATCHING, ADVANCED = (
    "How long a game runs", "Which games are listed", "Alerts", "What counts as watching",
    "Advanced — how games are found")
GROUPS = (GAME, LISTED, ALERTS, WATCHING, ADVANCED)

#: The overrides key for the user's All sports choices.
ALL = "all_sports"
#: Where a setting may be set: per sport only, All sports only, or both.
SPORT, ALL_ONLY, BOTH = "sport", "all", "both"


def sport_label(sport: str) -> str:
    """How the page and the prompt name *sport*: "All sports", "American Football"."""
    return "All sports" if sport == ALL else sport.replace("_", " ").title()


@dataclass(frozen=True)
class Spec:
    """One setting: its key, where it shows, its unit and range, and the field it fills."""

    key: str
    label: str
    group: str
    unit: str            # "hm" (minutes, shown as h/min), "min", "h", "days", "s", "n" (a count)
    lo: int
    hi: int
    suffix: str
    tip: str
    field: str           # the SportSettings field
    scope: str = BOTH    # SPORT, ALL_ONLY or BOTH

    def settable_for(self, sport: str) -> bool:
        """May the user set this for *sport* (or :data:`ALL`)?"""
        return self.scope == BOTH or (self.scope == ALL_ONLY) == (sport == ALL)

    def as_field(self, value: int):
        """The value as the ``SportSettings`` field wants it: a duration, or a plain
        number for the fields named for their unit (``_min``, ``_s``, ``_days``)."""
        if self.field.endswith(("_min", "_s", "_days", "_games")):
            return int(value)
        unit = {"hm": "minutes", "min": "minutes", "h": "hours", "days": "days", "s": "seconds"}
        return timedelta(**{unit[self.unit]: value})

    def text(self, value: int) -> str:
        """The value as the page and the prompt write it: "2 h 45 min", "30 days"."""
        if self.unit == "hm":
            return f"{value // 60} h {value % 60:02d} min"
        return f"{value}{self.suffix}"


SPECS: tuple[Spec, ...] = (
    Spec("usual_length", "Usual length:", GAME, "hm", 30, 720, "",
         "After this, a game on now shows as likely ending", "usual_length", scope=SPORT),
    Spec("long_limit", "Longest a game runs:", GAME, "hm", 30, 720, "",
         "After this, a game counts as finished", "long_limit", scope=SPORT),
    Spec("still_on_adds", "\"Still on\" adds:", GAME, "min", 5, 180, " min",
         "Right-click a finished game and choose \"Not finished — still on\": how much "
         "longer it stays on", "still_on_adds", scope=SPORT),
    Spec("still_on_window", "Offer \"Still on\" for:", GAME, "h", 1, 48, " h",
         "How long after a game's start the \"still on\" choice is offered", "still_on_window", scope=SPORT),
    Spec("listed_back", "Show finished games from the last:", LISTED, "h", 1, 72, " h",
         "How far back finished games stay listed", "window_back"),
    Spec("listed_ahead", "Show games up to:", LISTED, "h", 6, 168, " h ahead",
         "How far ahead games are listed", "window_ahead"),
    Spec("alert_keep", "Keep a one-game alert for:", ALERTS, "h", 1, 72, " h after the start",
         "A bell set on one game is removed this long after the game started", "alert_keep"),
    Spec("start_grace", "\"Starting now\" may still notify up to:", ALERTS, "min", 0, 60, " min late",
         "If the app checks late, the \"Starting now\" notice can still come this long after "
         "the start", "start_grace"),
    Spec("watched_after", "A play counts as watched after:", WATCHING, "s", 5, 600, " s",
         "Shorter plays (trying a channel) don't count as watching it", "watched_after_s"),
    Spec("watch_early", "Tuning in up to:", WATCHING, "min", 0, 60, " min before the start",
         "Starting a game's channel this long before it begins counts as watching the game",
         "watch_early"),
    Spec("most_watched_days", "\"Most watched\" looks back:", WATCHING, "days", 7, 365, " days",
         "The days of viewing that order sports and leagues by Most watched",
         "most_watched_days", scope=ALL_ONLY),
    Spec("report_days", "A channel report counts for:", WATCHING, "days", 1, 365, " days",
         "How long \"Nothing showing\" or \"Not this game\" keeps a channel marked (longer "
         "for repeated reports)", "report_days"),
    Spec("report_back", "Watching takes a report back after:", WATCHING, "min", 1, 60, " min",
         "Watching a reported channel this long takes one report back. Kept apart from "
         "\"counts as watched\": a black screen left running still counts", "report_back_min",
         scope=ALL_ONLY),
    Spec("same_game", "Listings of one game start within:", ADVANCED, "min", 15, 240, " min",
         "Two listings of the same two teams this close together are one game", "same_game"),
    Spec("replay_within", "A replay airs within:", ADVANCED, "h", 12, 240, " h",
         "A listing of the same two teams this long after a confirmed game is a replay",
         "replay_within"),
    Spec("stale_after", "A dateless listing is stale after:", ADVANCED, "h", 12, 240, " h",
         "A channel name with a time but no date, unchanged this long, is left over",
         "stale_after"),
    Spec("guide_join", "A guide programme with no teams joins a game within:", ADVANCED, "min",
         0, 60, " min", "A guide programme that names no teams joins the one game starting "
         "this close to it", "teamless_guide_within"),
    Spec("clock_agree", "Collections' clocks agree within:", ADVANCED, "min", 5, 120, " min",
         "How closely a collection's times must match known start times for its clock to be "
         "learned", "clock_agree_min", scope=ALL_ONLY),
    Spec("clock_keep", "Keep clock evidence for:", ADVANCED, "days", 1, 90, " days",
         "How long the start times a clock was learned from are kept", "clock_keep", scope=ALL_ONLY),
    Spec("usual_hours_off", "A guide-only game is a replay this far from usual start times:", ADVANCED,
         "h", 1, 12, " h", "A game only the guide lists, starting this far from the times this "
         "league's confirmed games start, is a rerun (a morning-after replay abroad)",
         "usual_hours_off"),
    Spec("usual_hours_games", "Usual start times need at least:", ADVANCED, "n", 1, 50,
         " confirmed games", "How many confirmed games a league needs before its usual start "
         "times are used", "usual_hours_min_games"),
    Spec("usual_hours_keep", "Remember start times for:", ADVANCED, "days", 7, 365, " days",
         "How long confirmed games' start times are kept to learn a league's usual times",
         "usual_hours_keep_days"),
)
BY_KEY: dict[str, Spec] = {s.key: s for s in SPECS}


@lru_cache(maxsize=1)
def _bundled() -> dict:
    with open(_BUNDLED_DEFINITIONS) as f:
        return (yaml.safe_load(f) or {}).get("sport_defaults") or {}


def defaults(sport: Optional[str] = None) -> dict[str, int]:
    """Every setting's default for *sport* (the ``default`` block, then the sport's own;
    a sport's block never moves an All-sports-only setting)."""
    data = _bundled()
    out = {k: int(v) for k, v in (data.get("default") or {}).items() if k in BY_KEY}
    missing = set(BY_KEY) - set(out)
    if missing:
        raise ValueError(f"sport_defaults.default is missing {sorted(missing)}")
    if sport and sport != ALL:
        out.update({k: int(v) for k, v in (data.get(sport) or {}).items()
                    if k in BY_KEY and BY_KEY[k].scope != ALL_ONLY})
    return out


def chosen(overrides: Optional[Mapping], sport: str) -> dict[str, list]:
    """The user's stored choices for *sport* (or :data:`ALL`):
    ``{key: [value, default_when_chosen]}``, only settings settable there."""
    return {k: list(v) for k, v in ((overrides or {}).get(sport) or {}).items()
            if k in BY_KEY and BY_KEY[k].settable_for(sport)}


def values(sport: str, overrides: Optional[Mapping] = None) -> dict[str, int]:
    """What each setting is for *sport*: the user's choice for it, else the user's
    All sports choice, else the default. For :data:`ALL`: its choices, else defaults."""
    out = defaults(sport)
    if sport != ALL:
        out.update({k: int(v[0]) for k, v in chosen(overrides, ALL).items()})
    out.update({k: int(v[0]) for k, v in chosen(overrides, sport).items()})
    return out


def inherited(sport: str, overrides: Optional[Mapping]) -> dict[str, int]:
    """For a sport: the All sports choices it follows (those it does not set itself)."""
    if sport == ALL:
        return {}
    own = chosen(overrides, sport)
    return {k: int(v[0]) for k, v in chosen(overrides, ALL).items()
            if k not in own and BY_KEY[k].settable_for(sport)}


def settings_kwargs(vals: Mapping[str, int]) -> dict:
    """*vals* as ``SportSettings`` keyword arguments."""
    return {BY_KEY[k].field: BY_KEY[k].as_field(v) for k, v in vals.items() if k in BY_KEY}


def set_choice(overrides: dict, sport: str, key: str, value: int) -> None:
    """Store the user's *value* for *key* — even when it equals today's default."""
    if not BY_KEY[key].settable_for(sport):
        raise ValueError(f"{key} is not set per {sport_label(sport)}")
    overrides.setdefault(sport, {})[key] = [int(value), defaults(sport)[key]]


def reset(overrides: dict, sport: str, key: Optional[str] = None) -> None:
    """Forget the user's choice (one *key*, or the whole sport): follow the defaults."""
    if key is None:
        overrides.pop(sport, None)
        return
    mine = overrides.get(sport) or {}
    mine.pop(key, None)
    if not mine:
        overrides.pop(sport, None)


@dataclass(frozen=True)
class Improved:
    """A stored choice whose default has moved since the user chose."""

    sport: str
    key: str
    yours: int
    new: int
    was: int


def improved(overrides: Optional[Mapping]) -> list[Improved]:
    """Every stored choice whose default changed since it was chosen."""
    out = []
    for sport in sorted((overrides or {}).keys()):
        now = defaults(sport)
        for key, (value, was) in sorted(chosen(overrides, sport).items()):
            if int(was) != now[key]:
                out.append(Improved(sport, key, int(value), now[key], int(was)))
    return out


def keep_mine(overrides: dict, item: Improved) -> None:
    """Keep the user's value; note the new default so this change is not asked again."""
    overrides.setdefault(item.sport, {})[item.key] = [item.yours, item.new]


def take_new(overrides: dict, item: Improved) -> None:
    """Take the new default: the choice is forgotten, the setting follows the defaults."""
    reset(overrides, item.sport, item.key)
