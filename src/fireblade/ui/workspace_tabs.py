"""Simple wrapping tab rows without a second copy of document data."""
from PySide6.QtCore import Signal, QTimer,Qt,QEvent
from PySide6.QtWidgets import QTabBar, QVBoxLayout, QWidget,QScrollArea,QFrame


class DocumentTabBar(QTabBar):
    """Keep the clicked widget alive across nested document-switch loops."""
    def __init__(self,owner):
        super().__init__(owner.content)
        self.owner=owner

    def mousePressEvent(self,event):
        self.owner._pressed_bar=self
        super().mousePressEvent(event)

    def mouseReleaseEvent(self,event):
        try:super().mouseReleaseEvent(event)
        finally:
            if self.owner._pressed_bar is self:self.owner._pressed_bar=None
            self.owner.finish_interaction()

    def event(self,event):
        owner=getattr(self,'owner',None)
        if owner is not None and event.type() in (QEvent.UngrabMouse,QEvent.WindowDeactivate,QEvent.Hide) and getattr(owner,'_pressed_bar',None) is self:
            owner._pressed_bar=None;owner.finish_interaction()
        return super().event(event)


class WorkspaceTabs(QWidget):
    currentChanged = Signal(int)
    tabCloseRequested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels, self.tips, self.active = [], [], -1
        self.multiline, self.pending = False, False
        self.rows = []
        self._building = False
        self._reschedule=False
        self._interaction_depth=0
        self._pressed_bar=None
        self.visible_row_limit=3
        self._signature = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.rebuild)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.area=QScrollArea(self)
        self.area.setFrameShape(QFrame.NoFrame)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.area.setWidgetResizable(True)
        self.area.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        self.content=QWidget()
        self.row_layout=QVBoxLayout(self.content)
        self.row_layout.setContentsMargins(0,0,0,0);self.row_layout.setSpacing(0)
        self.area.setWidget(self.content)
        self.layout.addWidget(self.area)
        self.area.viewport().installEventFilter(self)


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
            self._interaction_depth+=1
            try:self.currentChanged.emit(index)
            finally:
                self._interaction_depth-=1;self.finish_interaction()
        self.update_active()

    def request_close(self,index):
        self._interaction_depth+=1
        try:self.tabCloseRequested.emit(index)
        finally:
            self._interaction_depth-=1;self.finish_interaction()

    def finish_interaction(self):
        if not self._interaction_depth and self._pressed_bar is None and self._reschedule:
            self._reschedule=False;self.schedule()

    def replace_documents(self, labels, tips, active):
        changed = self.labels != labels or self.tips != tips
        self.labels, self.tips, self.active = list(labels), list(tips), active
        if changed:
            self.schedule()
        else:
            self.update_active()

    def update_active(self):
        offset = 0
        active_bar=None
        for bar in self.rows:
            if offset<=self.active<offset+bar.count():active_bar=bar
            bar.blockSignals(True)
            bar.setCurrentIndex(self.active - offset if offset <= self.active < offset + bar.count() else -1)
            bar.blockSignals(False)
            offset += bar.count()
        if active_bar is not None:self.area.ensureWidgetVisible(active_bar,0,0)

    def tab_widget(self, index):
        if self.pending:
            self.rebuild()
        self.layout.activate()
        self.row_layout.activate()
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
        if self._building or self._interaction_depth or self._pressed_bar is not None:
            self._reschedule=True
            return
        if not self.pending:
            self.pending = True
            self._timer.start(0)

    def rebuild(self):
        if self._interaction_depth or self._pressed_bar is not None:
            self._timer.stop();self.pending=False;self._reschedule=True;return
        self._timer.stop()
        self.pending = False
        signature = (tuple(self.labels), tuple(self.tips), self.multiline, self.area.viewport().width(), self.font().toString())
        if signature == self._signature:
            self.update_active()
            return
        self._signature = signature
        self._building = True
        for bar in self.rows:
            self.row_layout.removeWidget(bar)
            bar.deleteLater()
        self.rows = []
        partitions, current, width = [], [], 0
        for index, label in enumerate(self.labels):
            size = min(400, self.fontMetrics().horizontalAdvance(label) + 55)
            if self.multiline and current and width + size > max(150, self.area.viewport().width()):
                partitions.append(current)
                current, width = [], 0
            current.append(index)
            width += size
        if current:
            partitions.append(current)
        for indices in partitions:
            bar = DocumentTabBar(self)
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
            bar.tabCloseRequested.connect(lambda local, items=indices: self.request_close(items[local]))
            self.row_layout.addWidget(bar)
            bar.show()
            self.rows.append(bar)
        total=sum(bar.sizeHint().height() for bar in self.rows)
        row_height=max((bar.sizeHint().height() for bar in self.rows),default=0)
        self.content.setMinimumHeight(total)
        self.setFixedHeight(min(total,row_height*self.visible_row_limit))
        self.area.verticalScrollBar().setSingleStep(max(1,row_height))
        self.row_layout.activate();self.layout.activate()
        self._building = False
        self.update_active()
        if self._reschedule:
            self._reschedule=False;self.schedule()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.multiline and event.oldSize().width() != event.size().width():
            self.schedule()


    def eventFilter(self,watched,event):
        if watched is self.area.viewport() and event.type()==QEvent.Resize and self.multiline:self.schedule()
        return super().eventFilter(watched,event)
