"""Player plugin system for StreamSelect"""

from streamselect.core.players.base import PlayerPlugin
from streamselect.core.players.mpv import MPVPlayer

__all__ = ["PlayerPlugin", "MPVPlayer"]
