"""Simple wrapping tab rows without a second copy of document data."""
from PySide6.QtCore import Signal, QTimer
from PySide6.QtWidgets import QTabBar, QVBoxLayout, QWidget


class WorkspaceTabs(QWidget):
    currentChanged = Signal(int)
    tabCloseRequested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels, self.tips, self.active = [], [], -1
        self.multiline, self.pending = False, False
        self.rows = []
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

    def count(self):
        return len(self.labels)

    def addTab(self, label):
        self.labels.append(label)
        self.tips.append("")
        self.schedule()
        return len(self.labels) - 1

    def removeTab(self, index):
        del self.labels[index]
        del self.tips[index]
        self.schedule()

    def setTabToolTip(self, index, text):
        self.tips[index] = text
        self.schedule()

    def setCurrentIndex(self, index):
        if self.active != index:
            self.active = index
            self.currentChanged.emit(index)
        self.schedule()

    def tabRect(self, index):
        from PySide6.QtCore import QRect
        offset = 0
        for bar in self.rows:
            if offset <= index < offset + bar.count():
                rect = bar.tabRect(index - offset)
                return QRect(bar.mapTo(self, rect.topLeft()), rect.size())
            offset += bar.count()
        return QRect()

    def currentIndex(self):
        return self.active

    def setExpanding(self, _value):
        pass

    def setTabsClosable(self, _value):
        pass

    def setUsesScrollButtons(self, _value):
        pass

    def set_multiline(self, value):
        self.multiline = value
        self.schedule()

    def schedule(self):
        if not self.pending:
            self.pending = True
            QTimer.singleShot(0, self.rebuild)

    def rebuild(self):
        self.pending = False
        for bar in self.rows:
            self.layout.removeWidget(bar)
            bar.deleteLater()
        self.rows = []
        partitions, current, width = [], [], 0
        for index, label in enumerate(self.labels):
            size = min(400, self.fontMetrics().horizontalAdvance(label) + 55)
            if self.multiline and current and width + size > max(150, self.width()):
                partitions.append(current)
                current, width = [], 0
            current.append(index)
            width += size
        if current:
            partitions.append(current)
        for indices in partitions:
            bar = QTabBar(self)
            bar.setExpanding(False)
            bar.setTabsClosable(True)
            bar.setUsesScrollButtons(True)
            for index in indices:
                local = bar.addTab(self.labels[index])
                bar.setTabToolTip(local, self.tips[index])
            bar.setCurrentIndex(indices.index(self.active) if self.active in indices else -1)
            bar.currentChanged.connect(lambda local, items=indices: self.setCurrentIndex(items[local]) if local >= 0 else None)
            bar.tabCloseRequested.connect(lambda local, items=indices: self.tabCloseRequested.emit(items[local]))
            self.layout.addWidget(bar)
            self.rows.append(bar)
        self.setFixedHeight(sum(bar.sizeHint().height() for bar in self.rows))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.multiline:
            self.schedule()
