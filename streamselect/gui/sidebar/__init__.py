"""streamselect.gui.sidebar — collapsible sidebar section widgets."""

from streamselect.gui.sidebar.base import CollapsibleSection
from streamselect.gui.sidebar.alerts import WatchAlertsSection
from streamselect.gui.sidebar.history import HistorySection
from streamselect.gui.sidebar.favorites import FavoritesSection
from streamselect.gui.sidebar.recommended import RecommendedSection
from streamselect.gui.sidebar.queue import WatchQueueSection

__all__ = [
    "CollapsibleSection",
    "WatchAlertsSection",
    "HistorySection",
    "FavoritesSection",
    "RecommendedSection",
    "WatchQueueSection",
]
