"""Two synchronized views of one model; pinned cells are never duplicated in RAM."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHeaderView, QTreeView
from fireblade.ui.grid import GridDelegate


class PinnedTree(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pinned = []
        self.frozen = QTreeView(self)
        self.frozen.hide()
        self.frozen.setItemDelegate(GridDelegate(self.frozen))
        self.frozen.setUniformRowHeights(True)
        self.frozen.setAlternatingRowColors(True)
        self.frozen.setSelectionBehavior(QTreeView.SelectRows)
        self.frozen.setSelectionMode(QTreeView.ExtendedSelection)
        self.frozen.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.frozen.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.frozen.header().setSectionResizeMode(QHeaderView.Interactive)
        self.frozen.header().setStretchLastSection(False)
        self.frozen.setFocusProxy(self)
        self.frozen.setIndentation(16)
        self._syncing = False
        self._widths = {}
        self.verticalScrollBar().valueChanged.connect(self.frozen.verticalScrollBar().setValue)
        self.frozen.verticalScrollBar().valueChanged.connect(self.verticalScrollBar().setValue)
        self.expanded.connect(lambda i: self.frozen.setExpanded(i, True))
        self.collapsed.connect(lambda i: self.frozen.setExpanded(i, False))
        self.frozen.expanded.connect(lambda i: self.setExpanded(i, True))
        self.frozen.collapsed.connect(lambda i: self.setExpanded(i, False))
        self.frozen.header().sectionResized.connect(self.pin_resized)
        self.header().sectionResized.connect(lambda *_: self.position_pins())

    def setModel(self, model):
        if hasattr(self, 'frozen'):
            self.frozen.setModel(model)
        super().setModel(model)
        if model is not None:
            self.frozen.setSelectionModel(self.selectionModel())
            model.modelReset.connect(lambda: QTimer.singleShot(0, self.position_pins))
        self.set_pins([])

    def set_pins(self, columns):
        self._syncing = True
        try:
            for column in self.pinned:
                super().setColumnHidden(column, False)
            self.pinned = list(dict.fromkeys(columns))
            if self.model():
                for column in range(self.model().columnCount()):
                    self.frozen.setColumnHidden(column, column not in self.pinned)
                for position, column in enumerate(self.pinned):
                    width = self._widths.get(column) or self.columnWidth(column) or 150
                    self._widths[column] = width
                    self.frozen.setColumnWidth(column, width)
                    self.frozen.header().moveSection(self.frozen.header().visualIndex(column), position)
                    super().setColumnHidden(column, True)
            self.frozen.setVisible(bool(self.pinned) and self.model() is not None)
        finally:
            self._syncing = False
        self.position_pins()
        # A hidden QTreeView with all sections hidden can cache zero-height
        # items while rows arrive. Showing columns must rebuild that layout.
        self.frozen.doItemsLayout()
        self.frozen.viewport().update()

    def pin_resized(self, column, _old, width):
        if not self._syncing and column in self.pinned and width > 0:
            self._widths[column] = width
            self.position_pins()

    def position_pins(self):
        if self._syncing:
            return
        width = sum(self.frozen.columnWidth(col) for col in self.pinned) if self.model() else 0
        # Leave room for the other columns even if a pinned field is very wide.
        width = min(width, max(0, self.width() - 100))
        self.setViewportMargins(width, self.header().height(), 0, 0)
        frame = self.frameWidth()
        self.header().setGeometry(self.viewport().x(), frame, self.viewport().width(), self.header().height())
        self.frozen.setGeometry(frame, frame, width, self.viewport().height() + self.header().height())
        self.frozen.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_pins()
