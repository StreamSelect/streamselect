"""Collapsible splitter: left-click a handle to collapse, right-click to maximize."""
from PyQt6.QtWidgets import QSplitter, QSplitterHandle
from PyQt6.QtCore import Qt, QPointF, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QContextMenuEvent, QMouseEvent, QPainter

from streamselect.core import runtime_env
from streamselect.gui import theme as _theme
from streamselect.gui.cursor_affordance import set_resizable


class CollapsibleSplitterHandle(QSplitterHandle):
    """Custom splitter handle that collapses panels on click.

    The click-to-collapse gesture used to be invisible: a bare, near-zero-width
    handle with no affordance.  It now advertises itself — a minimum thickness
    (:data:`GRIP_THICKNESS`), a painted row of muted grip dots
    (:meth:`paintEvent`), a pointing-hand cursor (via the ``cursor_affordance``
    chokepoint), and a tooltip — so the collapse gesture is discoverable.
    """

    # Signal when handle is clicked (not dragged)
    clicked = pyqtSignal()
    #: Right-click, or whatever the platform's context gesture is (ctrl-click
    #: and two-finger click on macOS) — hence contextMenuEvent, not a button test.
    maximize_requested = pyqtSignal()

    #: Minimum handle thickness (px) so the grip dots have room to show — a bare
    #: QSplitterHandle is near-zero-width on most styles.
    GRIP_THICKNESS = 14
    #: macOS: a narrow strip is a hard target on a Retina trackpad, and the
    #: handle had the pointing hand rather than the resize arrows macOS users
    #: look for — "hard to grab on Mac, fine on Linux" (user report).
    MAC_GRIP_THICKNESS = 24
    #: Number / geometry of the centred grip dots painted on the handle.
    _GRIP_DOTS = 3
    _GRIP_DOT_RADIUS = 1.0
    _GRIP_DOT_GAP = 4.0

    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.drag_started = False
        self.click_pos = None
        # Discoverability: tooltip + the platform's resize arrows, on every
        # platform. Dragging is the primary gesture, and the arrows are what
        # says "this column can be resized" (user report — macOS got them
        # first). Through the cursor_affordance chokepoint, never
        # a hand-rolled setCursor here.
        self.setToolTip("Drag to resize · click to collapse/expand · right-click to maximize/restore")
        set_resizable(self, orientation)

    @classmethod
    def grip_thickness(cls) -> int:
        """Handle thickness for this platform (wider on macOS)."""
        return cls.MAC_GRIP_THICKNESS if runtime_env.is_macos() else cls.GRIP_THICKNESS

    def sizeHint(self) -> QSize:
        """Guarantee enough thickness across the handle to show the grip dots."""
        hint = super().sizeHint()
        if self.orientation() == Qt.Orientation.Horizontal:
            # Horizontal splitter → vertical handle strip: thickness is the WIDTH.
            hint.setWidth(max(hint.width(), self.grip_thickness()))
        else:
            hint.setHeight(max(hint.height(), self.grip_thickness()))
        return hint

    def paintEvent(self, event) -> None:
        """Draw the default handle, then a centred row of muted grip dots.

        The dots run along the handle's long axis (a horizontal splitter has
        vertical handle strips → dots stack vertically) so the affordance reads
        the same on every orientation.
        """
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(_theme.COLOR_SPLITTER_GRIP))

        rect = self.rect()
        cx = rect.center().x()
        cy = rect.center().y()
        span = self._GRIP_DOT_GAP * (self._GRIP_DOTS - 1)
        r = self._GRIP_DOT_RADIUS
        if self.orientation() == Qt.Orientation.Horizontal:
            # Vertical strip → stack the dots vertically, centred.
            top = cy - span / 2.0
            for i in range(self._GRIP_DOTS):
                painter.drawEllipse(QPointF(cx, top + i * self._GRIP_DOT_GAP), r, r)
        else:
            # Horizontal strip → lay the dots out horizontally, centred.
            left = cx - span / 2.0
            for i in range(self._GRIP_DOTS):
                painter.drawEllipse(QPointF(left + i * self._GRIP_DOT_GAP, cy), r, r)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        """Track mouse press for click detection"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_started = False
            self.click_pos = event.pos()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Detect if user is dragging"""
        if self.click_pos:
            # If moved more than 5 pixels, consider it a drag
            if (event.pos() - self.click_pos).manhattanLength() > 5:
                self.drag_started = True
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle click vs drag"""
        if event.button() == Qt.MouseButton.LeftButton:
            # If not dragged, emit clicked signal
            if not self.drag_started and self.click_pos:
                self.clicked.emit()
            self.drag_started = False
            self.click_pos = None
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Right-click maximizes; accepted so no parent's menu opens as well."""
        self.maximize_requested.emit()
        event.accept()


class CollapsibleSplitter(QSplitter):
    """Splitter whose handles collapse and maximize the panel they belong to.

    Features:
    - Left-click a handle to collapse/expand its panel
    - Right-click a handle to maximize/restore its panel
    - Drag handle to manually resize (standard behavior)
    - Remembers panel sizes before collapse or maximize
    """

    #: A handle gesture changed the layout. ``setSizes`` does not emit
    #: ``splitterMoved``, so nothing would otherwise persist the result.
    panels_toggled = pyqtSignal()

    def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.collapsed_panels = {}  # index -> previous_size
        # (maximized panel, panel that gave up the room, maximized panel's old size)
        self._maximized: tuple[int, int, int] | None = None
        # Only a drag emits this; a drag ends the maximize, so there is nothing
        # left to restore.
        self.splitterMoved.connect(self._forget_maximize)
        # Prevent Qt from collapsing panels to zero on drag — our click-to-collapse
        # logic calls setSizes() directly and still works with this off.
        self.setChildrenCollapsible(False)
        # Give handles a real thickness so the discoverable grip (see
        # CollapsibleSplitterHandle.paintEvent) has room to show; the handle's
        # sizeHint enforces the same floor.
        self.setHandleWidth(CollapsibleSplitterHandle.grip_thickness())
    
    def createHandle(self):
        """Create custom handle with click detection"""
        handle = CollapsibleSplitterHandle(self.orientation(), self)
        handle.clicked.connect(lambda: self._on_handle_clicked(handle))
        handle.maximize_requested.connect(lambda: self._on_handle_right_clicked(handle))
        return handle

    def _stretch(self, index: int) -> int:
        """The stretch factor ``setStretchFactor`` stored on panel *index*."""
        policy = self.widget(index).sizePolicy()
        if self.orientation() == Qt.Orientation.Horizontal:
            return policy.horizontalStretch()
        return policy.verticalStretch()

    def panel_for_handle(self, handle: CollapsibleSplitterHandle) -> int | None:
        """The panel a handle's gestures act on: its fixed neighbour, not the stretchy one.

        Handle *i* sits BEFORE panel *i* (handle 0 is the hidden one), so the
        handle between sidebar and content is index 1. Treating that index as
        the panel collapsed the CONTENT and left the sidebar filling its space,
        while the details handle (index 2) only looked right because the panel
        it should act on happens to share its number.

        Args:
            handle: A handle of this splitter.

        Returns:
            The panel index; the left/top neighbour when neither stretches
            more. ``None`` if *handle* has no panel before it.
        """
        after = self.indexOf(handle)
        if after < 1:
            return None
        before = after - 1
        return after if self._stretch(after) < self._stretch(before) else before

    def _on_handle_clicked(self, handle: CollapsibleSplitterHandle):
        """Left-click: collapse the handle's panel, or restore it if collapsed."""
        panel_index = self.panel_for_handle(handle)
        if panel_index is not None:
            self.toggle_panel(panel_index)
            self.panels_toggled.emit()

    def _on_handle_right_clicked(self, handle: CollapsibleSplitterHandle) -> None:
        """Right-click: maximize the handle's panel, or restore it if maximized."""
        panel_index = self.panel_for_handle(handle)
        if panel_index is not None:
            self.toggle_maximized(panel_index)
            self.panels_toggled.emit()

    def _forget_maximize(self, *_moved) -> None:
        self._maximized = None

    def _apply_sizes(self, sizes: list[int]) -> None:
        """``setSizes`` that may take a panel below its minimum, down to 0.

        childrenCollapsible is kept False to stop *drag* from collapsing panels,
        but that same flag also clamps setSizes() to a panel's minimumWidth — so
        a min-width panel (e.g. the 200px sidebar) would stick at ~200 instead
        of 0. Lift the flag only around this programmatic change, then restore
        it so drag protection stays intact.
        """
        was_collapsible = self.childrenCollapsible()
        self.setChildrenCollapsible(True)
        try:
            self.setSizes(sizes)
        finally:
            self.setChildrenCollapsible(was_collapsible)

    def settled_sizes(self) -> list[int]:
        """Panel sizes with any maximize undone: what a layout save should keep.

        A maximize is a moment, not a layout. Persisting its sizes would bring
        the app back next launch with the sidebar across the whole window.
        """
        sizes = self.sizes()
        if self._maximized is not None:
            index, absorber, previous = self._maximized
            room = sizes[index] + sizes[absorber]
            sizes[index] = previous
            sizes[absorber] = max(0, room - previous)
        return sizes

    def _restore_maximized(self) -> int | None:
        """Undo a maximize, if there is one.

        Returns:
            The panel that was maximized, or ``None``.
        """
        if self._maximized is None:
            return None
        sizes = self.settled_sizes()
        index = self._maximized[0]
        self._maximized = None
        self._apply_sizes(sizes)
        return index

    def maximize_panel(self, index: int) -> None:
        """Grow a panel over the stretching panel, leaving any other panel alone.

        The panel stops at its own maximum, and the stretching panel keeps
        whatever is left: the details pane tops out at 500px, so maximizing it
        does not empty the middle of the window.

        Args:
            index: Panel index to maximize.
        """
        if index < 0 or index >= self.count() or self.count() < 2:
            return
        self._restore_maximized()
        sizes = self.sizes()
        absorber = max(
            (i for i in range(len(sizes)) if i != index),
            key=lambda i: (self._stretch(i), -abs(i - index)),
        )
        panel = self.widget(index)
        ceiling = (panel.maximumWidth() if self.orientation() == Qt.Orientation.Horizontal
                   else panel.maximumHeight())
        room = sizes[index] + sizes[absorber]
        self._maximized = (index, absorber, sizes[index])
        sizes[index] = min(room, ceiling)
        sizes[absorber] = room - sizes[index]
        self._apply_sizes(sizes)

    def toggle_maximized(self, index: int) -> None:
        """Maximize a panel, or restore it if it is the one already maximized."""
        if self._restore_maximized() != index:
            self.maximize_panel(index)

    def is_panel_collapsed(self, index: int) -> bool:
        """Check if a panel is collapsed"""
        if index < 0 or index >= self.count():
            return False
        
        sizes = self.sizes()
        return sizes[index] == 0
    
    def collapse_panel(self, index: int):
        """Collapse a panel and remember its size"""
        if index < 0 or index >= self.count():
            return

        self._restore_maximized()
        sizes = self.sizes()
        current_size = sizes[index]

        if current_size > 0:
            # Remember current size
            self.collapsed_panels[index] = current_size

            sizes[index] = 0
            self._apply_sizes(sizes)
    
    def expand_panel(self, index: int):
        """Expand a collapsed panel back to the width it was collapsed from.

        The space has to be TAKEN BACK from the panels that absorbed it when
        this one collapsed. Writing the remembered width in and leaving the
        others alone asks the splitter for more room than it has, so Qt scales
        every panel down to fit and the restored panel comes back narrower than
        it went — visibly shrinking a little more on each collapse/expand cycle
        (a 416px sidebar returned as 327px). Same family as the an earlier change filter
        panel bug: a size request the splitter is free to ignore.

        Args:
            index: Panel index to restore.
        """
        if index < 0 or index >= self.count():
            return

        self._restore_maximized()

        # Get previous size or use default
        previous_size = self.collapsed_panels.get(index, 300)

        sizes = self.sizes()
        deficit = previous_size - sizes[index]
        if deficit > 0:
            # Reclaim from the WIDEST panel first, not proportionally from all
            # of them. The slack went to whichever panel grew when this one
            # collapsed — normally the centre content pane — so that is who
            # should give it back. Splitting the cost across every panel takes
            # width from the other flank too, which matters when both flanks
            # are restored in turn (leaving an Explore view does exactly that):
            # restoring the first would quietly shrink the second.
            for i in sorted(
                (i for i in range(len(sizes)) if i != index),
                key=lambda i: sizes[i],
                reverse=True,
            ):
                if deficit <= 0:
                    break
                take = min(deficit, sizes[i])
                sizes[i] -= take
                deficit -= take
        sizes[index] = previous_size
        # Through _apply_sizes: a plain setSizes would clamp the OTHER flank's 0
        # up to its minimum, so reopening the sidebar also popped details open.
        self._apply_sizes(sizes)

        # Clear remembered size
        if index in self.collapsed_panels:
            del self.collapsed_panels[index]
    
    def toggle_panel(self, index: int):
        """Toggle panel collapsed state; a maximized panel counts as open."""
        self._restore_maximized()
        if self.is_panel_collapsed(index):
            self.expand_panel(index)
        else:
            self.collapse_panel(index)
