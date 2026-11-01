"""Classic header-to-group-bar drag and drop, without loading extra rows."""
from PySide6.QtCore import QByteArray, QMimeData, Qt
from PySide6.QtGui import QDrag, QColor, QFontMetrics, QPalette
from PySide6.QtWidgets import QHeaderView, QLabel, QStyle, QStyleOptionHeader

MIME = "application/x-fireblade-column"


class GroupHeader(QHeaderView):
    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.pressed_position = None
        self.pressed_section = -1
        self.setSectionsClickable(True)

    def paintSection(self,painter,rect,logical):
        model=self.model()
        styles=getattr(getattr(model,'view',None),'layout_styles',{})
        from fireblade.ui.layout_styles import merge_styles
        appearance=merge_styles(styles.get('header',{}),styles.get(f'header:{logical-1}',{}))
        if not appearance:
            super().paintSection(painter,rect,logical)
            return
        from fireblade.ui.layout_styles import role_value,font_for,paint_image,paint_border,paint_text
        painter.save();painter.setClipRect(rect)
        background=role_value(appearance,Qt.BackgroundRole)
        painter.fillRect(rect,background if background is not None else self.palette().brush(QPalette.Button))
        painter.setPen(self.palette().color(QPalette.Mid));painter.drawLine(rect.bottomLeft(),rect.bottomRight());painter.drawLine(rect.topRight(),rect.bottomRight())
        paint_image(painter,rect,appearance)
        font=font_for(appearance,self.font());painter.setFont(font)
        painter.setPen(QColor(appearance['foreground']) if 'foreground' in appearance else self.palette().color(QPalette.ButtonText))
        content=rect.adjusted(5,2,-5,-2)
        if self.isSortIndicatorShown() and self.sortIndicatorSection()==logical:content.adjust(0,0,-16,0)
        label=str(model.headerData(logical,Qt.Horizontal) or '')
        alignment=role_value(appearance,Qt.TextAlignmentRole) or (Qt.AlignLeft|Qt.AlignVCenter)
        paint_text(painter,content,label,appearance,alignment)
        paint_border(painter,rect,appearance)
        if self.isSortIndicatorShown() and self.sortIndicatorSection()==logical:
            option=QStyleOptionHeader();self.initStyleOption(option)
            option.rect=rect.adjusted(rect.width()-17,2,-3,-2)
            option.sortIndicator=QStyleOptionHeader.SortDown if self.sortIndicatorOrder()==Qt.AscendingOrder else QStyleOptionHeader.SortUp
            self.style().drawPrimitive(QStyle.PE_IndicatorHeaderArrow,option,painter,self)
        painter.restore()

    def sectionSizeFromContents(self,logical):
        size=super().sectionSizeFromContents(logical)
        model=self.model();styles=getattr(getattr(model,'view',None),'layout_styles',{})
        from fireblade.ui.layout_styles import merge_styles
        appearance=merge_styles(styles.get('header',{}),styles.get(f'header:{logical-1}',{}))
        if appearance:
            from fireblade.ui.layout_styles import font_for
            size.setHeight(max(size.height(),QFontMetrics(font_for(appearance,self.font())).height()+8))
        size.setHeight(max(size.height(),getattr(model,'max_header_height',0)))
        return size

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
