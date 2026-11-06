"""Classic header-to-group-bar drag and drop, without loading extra rows."""
from PySide6.QtCore import QByteArray, QMimeData, Qt, QTimer, Signal, QRect
from PySide6.QtGui import QDrag, QColor, QFontMetrics, QPalette
from PySide6.QtWidgets import QHeaderView, QLabel, QStyle, QStyleOptionHeader, QLineEdit, QToolButton, QHBoxLayout

MIME = "application/x-fireblade-column"


class GroupHeader(QHeaderView):
    filterChanged = Signal(int, str)
    sortRequested = Signal(int, bool)

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.pressed_position = None
        self.pressed_section = -1
        self.setSectionsClickable(True)
        self.controls = {}
        self.pending = {}
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(450)
        self.timer.timeout.connect(self.flush_filters)
        self.sectionResized.connect(self.position_controls)
        self.sectionMoved.connect(self.position_controls)
        self.geometriesChanged.connect(self.position_controls)

    def sync_filters(self, filters, sort_column=None, descending=False):
        count = self.count()
        for section in list(self.controls):
            if section >= count:
                for widget in self.controls.pop(section):
                    widget.deleteLater()
        for section in range(1, count):
            if section not in self.controls:
                edit = QLineEdit(self.viewport())
                edit.setPlaceholderText("Contient…")
                edit.setClearButtonEnabled(True)
                edit.setAccessibleName(f"Filtrer la colonne {section}")
                edit.setToolTip("Contient ce texte · les filtres de colonnes se combinent avec ET")
                edit.textEdited.connect(lambda text, c=section-1: self.queue_filter(c, text))
                edit.returnPressed.connect(self.flush_filters)
                buttons = []
                for descending, arrow in [(False, Qt.UpArrow), (True, Qt.DownArrow)]:
                    button = QToolButton(self.viewport())
                    button.setArrowType(arrow)
                    button.setAutoRaise(True)
                    button.setCheckable(True)
                    label = "Tri décroissant" if descending else "Tri croissant"
                    button.setToolTip(label)
                    button.setAccessibleName(label)
                    button.clicked.connect(lambda checked=False, c=section-1, d=descending: self.sortRequested.emit(c, d))
                    buttons.append(button)
                self.controls[section] = (edit, *buttons)
            for direction, button in zip((False, True), self.controls[section][1:]):
                button.setChecked(sort_column == section-1 and descending == direction)
            value = next((f.value for f in filters if f.column == section-1 and f.operator == 'contains'), '')
            if section-1 not in self.pending:
                self.controls[section][0].setText(value)
        self.position_controls()

    def queue_filter(self, column, text):
        self.pending[column] = text
        self.timer.start()

    def flush_filters(self):
        self.timer.stop()
        pending, self.pending = self.pending, {}
        for column, text in pending.items():
            self.filterChanged.emit(column, text)

    def position_controls(self, *_):
        row_height = self.fontMetrics().height() + 12
        top_height = max(24, self.height() - row_height)
        for section, (edit, up, down) in self.controls.items():
            visible = section < self.count() and not self.isSectionHidden(section)
            x, width = self.sectionViewportPosition(section), self.sectionSize(section)
            edit.setGeometry(x+3, top_height+1, max(1, width-6), row_height-3)
            up.setGeometry(x+width-36, 1, 16, top_height-2)
            down.setGeometry(x+width-19, 1, 16, top_height-2)
            edit.setVisible(visible and width > 32)
            up.setVisible(visible and width > 60)
            down.setVisible(visible and width > 60)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_controls()

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self.position_controls()

    def paintEvent(self, event):
        self.position_controls()
        super().paintEvent(event)

    def paintSection(self,painter,rect,logical):
        rect = QRect(rect)
        rect.setHeight(max(24, rect.height() - self.fontMetrics().height() - 12))
        model=self.model()
        styles=getattr(getattr(model,'view',None),'layout_styles',{})
        from fireblade.ui.layout_styles import merge_styles
        appearance=merge_styles(styles.get('header',{}),styles.get(f'header:{logical-1}',{}))
        if not appearance:
            option = QStyleOptionHeader()
            self.initStyleOptionForIndex(option, logical)
            option.rect = rect
            option.text = self.fontMetrics().elidedText(option.text, Qt.ElideRight, max(0, rect.width()-44))
            option.sortIndicator = QStyleOptionHeader.None_
            painter.save()
            self.style().drawControl(QStyle.CE_Header, option, painter, self)
            painter.restore()
            return
        from fireblade.ui.layout_styles import role_value,font_for,paint_image,paint_border,paint_text
        painter.save();painter.setClipRect(rect)
        background=role_value(appearance,Qt.BackgroundRole)
        painter.fillRect(rect,background if background is not None else self.palette().brush(QPalette.Button))
        painter.setPen(self.palette().color(QPalette.Mid));painter.drawLine(rect.bottomLeft(),rect.bottomRight());painter.drawLine(rect.topRight(),rect.bottomRight())
        paint_image(painter,rect,appearance)
        font=font_for(appearance,self.font());painter.setFont(font)
        painter.setPen(QColor(appearance['foreground']) if 'foreground' in appearance else self.palette().color(QPalette.ButtonText))
        content=rect.adjusted(5,2,-40,-2)
        label=str(model.headerData(logical,Qt.Horizontal) or '')
        alignment=role_value(appearance,Qt.TextAlignmentRole) or (Qt.AlignLeft|Qt.AlignVCenter)
        paint_text(painter,content,label,appearance,alignment)
        paint_border(painter,rect,appearance)
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
        size.setHeight(size.height() + self.fontMetrics().height() + 12)
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


class GroupSeparator(QLabel):
    """Insertion point between two grouping levels; accepts a column drop."""

    def __init__(self, bar, position):
        super().__init__("\u203a", bar)
        self.bar, self.position = bar, position
        self.setAcceptDrops(True)
        self.setToolTip("Déposer ici pour insérer un niveau à cette position")

    def dragEnterEvent(self, event):
        self.bar.dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(MIME):
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.bar.drop_at(event, self.position)


class GroupBar(QLabel):
    """Grouping bar: numbered levels, per-level removal and one clear-all action.

    Headers are dragged from the grid header onto the bar (append) or between two
    levels (insert at that position), which is the ordering gesture analysts
    already know from spreadsheet tools.
    """

    def __init__(self, callback, parent=None):
        super().__init__("Glissez un en-tête ici pour regrouper", parent)
        self.callback = callback
        self.chips = QHBoxLayout(self)
        self.chips.setContentsMargins(6, 4, 6, 4)
        self.chips.setSpacing(6)
        self.setAcceptDrops(True)
        self.setMinimumHeight(30)
        self.clear_button = QToolButton(self)
        self.clear_button.setText("Tout supprimer")
        self.clear_button.setToolTip("Retirer tous les niveaux de regroupement")
        self.clear_button.setAutoRaise(True)
        self.clear_button.setVisible(False)
        self.clear_button.clicked.connect(lambda: self.callback(-1, clear=True))
        self.setToolTip("Glissez plusieurs en-têtes pour imbriquer les groupes. Regrouper… permet de modifier leur ordre.")

    def _reset(self):
        while self.chips.count():
            item = self.chips.takeAt(0)
            widget = item.widget()
            # The clear button survives rebuilds: it is reused, not recreated.
            if widget is not None and widget is not self.clear_button:
                widget.hide()
                widget.deleteLater()

    def set_groups(self, headers, groups):
        self._reset()
        self.clear_button.setVisible(bool(groups))
        if not groups:
            self.setText("Glissez un en-tête ici pour regrouper les résultats")
            return
        self.setText("")
        for level, column in enumerate(groups):
            if level:
                self.chips.addWidget(GroupSeparator(self, level))
            button = QToolButton(self)
            button.setText(f"{level+1}  {headers[column]}  \u00d7")
            button.setToolTip("Retirer ce niveau de regroupement")
            button.setAutoRaise(True)
            button.clicked.connect(lambda checked=False, c=column: self.callback(c, remove=True))
            self.chips.addWidget(button)
        hint = GroupSeparator(self, len(groups))
        hint.setText("+")
        hint.setToolTip("Déposer un en-tête ici pour ajouter un niveau à la fin")
        self.chips.addWidget(hint)
        self.chips.addStretch()
        self.chips.addWidget(self.clear_button)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(MIME):
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.drop_at(event, None)

    def drop_at(self, event, position):
        try:
            value = int(bytes(event.mimeData().data(MIME)).decode("ascii"))
        except (ValueError, UnicodeError):
            event.ignore()
            return
        event.acceptProposedAction()
        # Grouping rebuilds the grid inside dropEvent, which destroys the drag
        # source and leaves its pixmap on screen until something repaints the
        # header. Let the drag finish before touching the view.
        QTimer.singleShot(0, lambda: self.callback(value, append=True, position=position))
