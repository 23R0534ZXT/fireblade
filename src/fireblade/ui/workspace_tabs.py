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
        self._building = False
        self._signature = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.rebuild)
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
        self.update_active()

    def replace_documents(self, labels, tips, active):
        changed = self.labels != labels or self.tips != tips
        self.labels, self.tips, self.active = list(labels), list(tips), active
        if changed:
            self.schedule()
        else:
            self.update_active()

    def update_active(self):
        offset = 0
        for bar in self.rows:
            bar.blockSignals(True)
            bar.setCurrentIndex(self.active - offset if offset <= self.active < offset + bar.count() else -1)
            bar.blockSignals(False)
            offset += bar.count()

    def tab_widget(self, index):
        if self.pending:
            self.rebuild()
        self.layout.activate()
        offset = 0
        for bar in self.rows:
            if offset <= index < offset + bar.count():
                return bar, index - offset
            offset += bar.count()
        raise IndexError('Onglet introuvable')

    def tabRect(self, index):
        from PySide6.QtCore import QRect
        try:
            bar, local = self.tab_widget(index)
        except IndexError:
            return QRect()
        rect = bar.tabRect(local)
        return QRect(bar.mapTo(self, rect.topLeft()), rect.size())

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
        if not self.pending and not self._building:
            self.pending = True
            self._timer.start(0)

    def rebuild(self):
        self._timer.stop()
        self.pending = False
        signature = (tuple(self.labels), tuple(self.tips), self.multiline, self.width(), self.font().toString())
        if signature == self._signature:
            self.update_active()
            return
        self._signature = signature
        self._building = True
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
            # In another row, QTabBar can already consider local index 0 its
            # current item. A click must still activate that document globally.
            bar.tabBarClicked.connect(lambda local, items=indices: self.setCurrentIndex(items[local]) if local >= 0 else None)
            bar.tabCloseRequested.connect(lambda local, items=indices: self.tabCloseRequested.emit(items[local]))
            self.layout.addWidget(bar)
            bar.show()
            self.rows.append(bar)
        self.setFixedHeight(sum(bar.sizeHint().height() for bar in self.rows))
        self.layout.activate()
        self._building = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.multiline and event.oldSize().width() != event.size().width():
            self.schedule()
