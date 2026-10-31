"""Pinned views share one paged model and selection; no duplicated data rows."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHeaderView, QTreeView
from fireblade.ui.grid import GridDelegate


class PinnedTree(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pinned, self.right_pinned = [], []
        self._syncing = False
        self._positioning = False
        self._widths = {}
        self.setHorizontalScrollMode(QTreeView.ScrollPerPixel)
        self.frozen = self.make_panel()
        self.right_frozen = self.make_panel()
        self.right_frozen.setRootIsDecorated(False)
        self.right_frozen.setItemsExpandable(False)
        self.right_frozen.setIndentation(0)
        self.right_frozen.setTreePosition(0)
        self.header().sectionResized.connect(lambda *_: self.position_pins())

    @property
    def frozen_views(self):
        return self.frozen, self.right_frozen

    @property
    def all_pinned(self):
        return self.pinned + self.right_pinned

    def frozen_for(self, column):
        return self.right_frozen if column in self.right_pinned else self.frozen if column in self.pinned else self

    def make_panel(self):
        panel = QTreeView(self)
        panel.hide()
        panel.setFrameShape(QFrame.NoFrame)
        panel.setStyleSheet("QTreeView { border: 0; }")
        panel.setItemDelegate(GridDelegate(panel))
        panel.setUniformRowHeights(True)
        panel.setAlternatingRowColors(True)
        panel.setSelectionBehavior(QTreeView.SelectRows)
        panel.setSelectionMode(QTreeView.ExtendedSelection)
        panel.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        panel.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        panel.header().setSectionResizeMode(QHeaderView.Interactive)
        panel.header().setStretchLastSection(False)
        panel.setFocusProxy(self)
        panel.setIndentation(16)
        self.verticalScrollBar().valueChanged.connect(panel.verticalScrollBar().setValue)
        panel.verticalScrollBar().valueChanged.connect(self.verticalScrollBar().setValue)
        self.expanded.connect(lambda index, p=panel: p.setExpanded(index, True))
        self.collapsed.connect(lambda index, p=panel: p.setExpanded(index, False))
        panel.expanded.connect(lambda index: self.setExpanded(index, True))
        panel.collapsed.connect(lambda index: self.setExpanded(index, False))
        panel.header().sectionResized.connect(self.pin_resized)
        return panel

    def setModel(self, model):
        if hasattr(self, 'frozen'):
            for panel in self.frozen_views:
                panel.setModel(model)
        super().setModel(model)
        if model is not None:
            for panel in self.frozen_views:
                panel.setSelectionModel(self.selectionModel())
            model.modelReset.connect(lambda: QTimer.singleShot(0, self.position_pins))
        self.set_pins([])

    def set_pins(self, columns, right_columns=()):
        self._syncing = True
        try:
            for column in self.all_pinned:
                super().setColumnHidden(column, False)
                if column in self._widths:
                    self.setColumnWidth(column, self._widths[column])
            self.pinned = list(dict.fromkeys(columns))
            self.right_pinned = [c for c in dict.fromkeys(right_columns) if c not in self.pinned]
            if self.model():
                for panel, pinned in ((self.frozen, self.pinned), (self.right_frozen, self.right_pinned)):
                    for column in range(self.model().columnCount()):
                        panel.setColumnHidden(column, column not in pinned)
                    for position, column in enumerate(pinned):
                        width = self._widths.get(column) or self.columnWidth(column) or 150
                        self._widths[column] = width
                        panel.setColumnWidth(column, width)
                        panel.header().moveSection(panel.header().visualIndex(column), position)
                        super().setColumnHidden(column, True)
            for panel, pinned in ((self.frozen, self.pinned), (self.right_frozen, self.right_pinned)):
                panel.setVisible(bool(pinned) and self.model() is not None)
        finally:
            self._syncing = False
        self.position_pins()
        for panel in self.frozen_views:
            panel.doItemsLayout()
            panel.viewport().update()

    def pin_resized(self, column, _old, width):
        if not self._syncing and column in self.all_pinned and width > 0:
            self._widths[column] = width
            self.position_pins()

    def position_pins(self):
        if self._syncing or self._positioning:
            return
        self._positioning = True
        try:
            left = sum(self.frozen.columnWidth(c) for c in self.pinned) if self.model() else 0
            right = sum(self.right_frozen.columnWidth(c) for c in self.right_pinned) if self.model() else 0
            # Keep the center usable when fields are wide or the window is narrow.
            budget = max(0, self.width() - 100 - self.verticalScrollBar().sizeHint().width())
            total = left + right
            if total > budget:
                left = round(budget * left / total)
                right = budget - left
            self.setViewportMargins(left, self.header().height(), right, 0)
            frame = self.frameWidth()
            height = self.viewport().height() + self.header().height()
            self.header().setGeometry(self.viewport().x(), frame, self.viewport().width(), self.header().height())
            self.frozen.setGeometry(frame, frame, left, height)
            self.right_frozen.setGeometry(self.viewport().geometry().right() + 1, frame, right, height)
            self.horizontalScrollBar().setPageStep(self.viewport().width())
            self.horizontalScrollBar().setRange(0, max(0, self.header().length() - self.viewport().width()))
            for panel in self.frozen_views:
                panel.header().setFixedHeight(self.header().height())
                panel.raise_()
        finally:
            self._positioning = False

    def updateGeometries(self):
        if getattr(self, '_positioning', False):
            return
        super().updateGeometries()
        if hasattr(self, 'right_frozen'):
            self.position_pins()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_pins()
