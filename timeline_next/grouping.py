"""Classic header-to-group-bar drag and drop, without loading extra rows."""
from PySide6.QtCore import QByteArray, QMimeData, Qt
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QHeaderView, QLabel

MIME = "application/x-fireblade-column"


class GroupHeader(QHeaderView):
    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.pressed_position = None
        self.pressed_section = -1
        self.setSectionsClickable(True)

    def mousePressEvent(self, event):
        self.pressed_position = event.position().toPoint()
        self.pressed_section = self.logicalIndexAt(self.pressed_position)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (event.buttons() & Qt.LeftButton and self.pressed_position is not None
                and self.pressed_section > 0 and abs(event.position().y() - self.pressed_position.y()) > 22):
            mime = QMimeData()
            mime.setData(MIME, QByteArray(str(self.pressed_section - 1).encode("ascii")))
            drag = QDrag(self)
            drag.setMimeData(mime)
            self.pressed_position = None
            drag.exec(Qt.CopyAction)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.pressed_position = None
        super().mouseReleaseEvent(event)


class GroupBar(QLabel):
    def __init__(self, callback, parent=None):
        super().__init__("Glissez un en-tête ici pour regrouper", parent)
        self.callback = callback
        self.setAcceptDrops(True)
        self.setMinimumHeight(30)
        self.setToolTip("Glissez plusieurs en-têtes pour imbriquer les groupes. Regrouper… permet de modifier leur ordre.")

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        try:
            value = int(bytes(event.mimeData().data(MIME)).decode("ascii"))
        except (ValueError, UnicodeError):
            event.ignore()
            return
        self.callback(value, append=True)
        event.acceptProposedAction()
