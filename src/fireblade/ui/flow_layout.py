"""Wrap small tool rows so detached panels remain usable at narrow widths."""
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout


class FlowLayout(QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(5)

    def addItem(self, item):self.items.append(item)
    def addWidget(self, widget, *_):super().addWidget(widget)
    def addStretch(self, *_):pass
    def count(self):return len(self.items)
    def itemAt(self, index):return self.items[index] if 0 <= index < len(self.items) else None
    def takeAt(self, index):return self.items.pop(index) if 0 <= index < len(self.items) else None
    def expandingDirections(self):return Qt.Horizontal
    def hasHeightForWidth(self):return True
    def heightForWidth(self, width):return self.arrange(QRect(0, 0, width, 0), False)
    def setGeometry(self, rect):super().setGeometry(rect);self.arrange(rect, True)
    def sizeHint(self):return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.items:size = size.expandedTo(item.minimumSize())
        return size

    def arrange(self, rect, apply):
        x, y, height = rect.x(), rect.y(), 0
        for item in self.items:
            if item.isEmpty():continue
            size = item.sizeHint().expandedTo(item.minimumSize())
            size.setWidth(min(max(1, rect.width()), size.width()))
            if x > rect.x() and x + size.width() > rect.right()+1:
                x = rect.x();y += height+self.spacing();height = 0
            if apply:item.setGeometry(QRect(QPoint(x,y),size))
            x += size.width()+self.spacing();height = max(height,size.height())
        return y+height-rect.y()
