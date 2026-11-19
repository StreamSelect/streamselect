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


@dataclass(frozen=True)
class Spec:
    """One setting: its key, where it shows, its unit and range, and the field it fills."""

    key: str
    label: str
    group: str
    unit: str            # "hm" (minutes, shown as h/min), "min", "h", "days", "s"
    lo: int
    hi: int
    suffix: str
    tip: str
    field: str           # the SportSettings field

    def as_field(self, value: int):
        """The value as the ``SportSettings`` field wants it: a duration, or a plain
        number for the fields named for their unit (``_min``, ``_s``, ``_days``)."""
        if self.field.endswith(("_min", "_s", "_days")):
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
         "After this, a game on now shows as likely ending", "usual_length"),
    Spec("long_limit", "Longest a game runs:", GAME, "hm", 30, 720, "",
         "After this, a game counts as finished", "long_limit"),
    Spec("still_on_adds", "\"Still on\" adds:", GAME, "min", 5, 180, " min",
         "Right-click a finished game and choose \"Not finished — still on\": how much "
         "longer it stays on", "still_on_adds"),
    Spec("still_on_window", "Offer \"Still on\" for:", GAME, "h", 1, 48, " h",
         "How long after a game's start the \"still on\" choice is offered", "still_on_window"),
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
         "most_watched_days"),
    Spec("report_days", "A channel report counts for:", WATCHING, "days", 1, 365, " days",
         "How long \"Nothing showing\" or \"Not this game\" keeps a channel marked (longer "
         "for repeated reports)", "report_days"),
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
         "learned", "clock_agree_min"),
    Spec("clock_keep", "Keep clock evidence for:", ADVANCED, "days", 1, 90, " days",
         "How long the start times a clock was learned from are kept", "clock_keep"),
)
BY_KEY: dict[str, Spec] = {s.key: s for s in SPECS}


@lru_cache(maxsize=1)
def _bundled() -> dict:
    with open(_BUNDLED_DEFINITIONS) as f:
        return (yaml.safe_load(f) or {}).get("sport_defaults") or {}


def defaults(sport: Optional[str] = None) -> dict[str, int]:
    """Every setting's default for *sport* (the ``default`` block, then the sport's own)."""
    data = _bundled()
    out = {k: int(v) for k, v in (data.get("default") or {}).items() if k in BY_KEY}
    missing = set(BY_KEY) - set(out)
    if missing:
        raise ValueError(f"sport_defaults.default is missing {sorted(missing)}")
    if sport:
        out.update({k: int(v) for k, v in (data.get(sport) or {}).items() if k in BY_KEY})
    return out


def chosen(overrides: Optional[Mapping], sport: str) -> dict[str, list]:
    """The user's stored choices for *sport*: ``{key: [value, default_when_chosen]}``."""
    return {k: list(v) for k, v in ((overrides or {}).get(sport) or {}).items() if k in BY_KEY}


def values(sport: str, overrides: Optional[Mapping] = None) -> dict[str, int]:
    """What each setting is for *sport*: the user's choice, else the default."""
    out = defaults(sport)
    out.update({k: int(v[0]) for k, v in chosen(overrides, sport).items()})
    return out


def settings_kwargs(vals: Mapping[str, int]) -> dict:
    """*vals* as ``SportSettings`` keyword arguments."""
    return {BY_KEY[k].field: BY_KEY[k].as_field(v) for k, v in vals.items() if k in BY_KEY}


def set_choice(overrides: dict, sport: str, key: str, value: int) -> None:
    """Store the user's *value* for *key* — even when it equals today's default."""
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
