"""Stored games: what the game finder decided, for every screen to read.

Replaced whole on every run of the finder (the input is the whole live list,
so the output is too). Screens read these rows and never parse a channel name
for a game again. ``database.py`` imports this module so ``create_all`` makes
the tables; new tables need no migration entry, a new COLUMN does
(``core/schema_migrations.py``).
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from streamselect.core.db_base import Base, JSONEncoded


class GameDB(Base):
    """One game: two sides and a start, with its confidence level (1 best, 4 worst)."""
    __tablename__ = "games"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    sport       = Column(String, nullable=False)
    league      = Column(String, nullable=False)
    team_a      = Column(String, nullable=False)    # display names, alphabetical
    team_b      = Column(String, nullable=False)
    start_utc   = Column(DateTime, nullable=False)
    level       = Column(Integer, nullable=False)
    replay      = Column(Boolean, nullable=False, default=False)
    collections = Column(Integer, nullable=False)   # independent collections that agree
    found_at    = Column(DateTime, nullable=False, default=datetime.utcnow)
    #: The home side (team_a or team_b) when the listings say "away @ / at home"; else NULL.
    home_team   = Column(String)

    feeds = relationship("GameFeedDB", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_games_sport_start", "sport", "start_utc"),)


class GameFeedDB(Base):
    """One listing of a game: a channel, or a guide programme (``from_guide``)."""
    __tablename__ = "game_feeds"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    game_id    = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True)
    channel_id = Column(String, index=True)          # None for a guide programme with no channel link
    source     = Column(String, nullable=False)      # provider id, or "guide"
    collection = Column(String, nullable=False)
    name       = Column(String, nullable=False)
    from_guide = Column(Boolean, nullable=False, default=False)
    #: How its start was read: "zone", "clock", "guide", or "" (joined by teams alone).
    time_from  = Column(String, nullable=False, default="")
    start_utc  = Column(DateTime)
    #: Counted toward the level; a teamless guide programme is a feed, never evidence.
    counts     = Column(Boolean, nullable=False, default=True)


class GameFinderMemoryDB(Base):
    """What one run of a league's finder hands the next.

    Learned clocks, when each name was first seen, and recent Level 1 games.
    """
    __tablename__ = "game_finder_memory"

    #: "<sport>/<league>": each league is found on its own.
    finder     = Column(String, primary_key=True)
    memory     = Column(JSONEncoded, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class GameEndDB(Base):
    """A game the user marked finished (Sports, right-click → Mark as finished).

    Keyed by the game itself, not ``games.id``: the games table is rebuilt on
    every finder run. Each row is also a measured game length for its league —
    the data that will replace ``SportSettings.usual_length`` over time.
    """
    __tablename__ = "game_ends"

    league_key = Column(String, primary_key=True)    # "hockey/NHL"
    team_a     = Column(String, primary_key=True)
    team_b     = Column(String, primary_key=True)
    start_utc  = Column(DateTime, primary_key=True)
    ended_at   = Column(DateTime, nullable=False)    # UTC, when the user marked it
