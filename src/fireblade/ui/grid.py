"""Paged Qt model; no dialogs or window controls."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, Signal, QPoint, QRect, QEvent
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPolygon, QPalette, QBrush
from PySide6.QtWidgets import QStyledItemDelegate, QStyle

from fireblade.core.models import View
from fireblade.core.conditions import validate_format_rules
from fireblade.ui.visual_rules import VISUAL_ROLE, BAR_ROLE, ICON_ROLE, visual_value, contrast_color, icon_image, icon_level
from fireblade.ui.workers import Job


class GridDelegate(QStyledItemDelegate):
    """Draw grid lines without a stylesheet that overrides model colors."""
    def editorEvent(self, event, model, option, index):
        if index.column() == 0 and not model.node(index).group and not model.node(index).footer:
            if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                checked = model.data(index, Qt.CheckStateRole) == Qt.Checked
                return model.setData(index, Qt.Unchecked if checked else Qt.Checked, Qt.CheckStateRole)
            if event.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick):
                return True
        return super().editorEvent(event, model, option, index)

    def initStyleOption(self,option,index):
        super().initStyleOption(option,index)
        selected=bool(option.state & QStyle.State_Selected)
        from fireblade.ui.layout_styles import merge_styles
        states=self.state_layers(index,option)
        layers=self.appearance_layers(index,option)
        appearance=merge_styles(*states)
        appearance.update(merge_styles(*layers,priority_only=True))
        if appearance:
            from fireblade.ui.layout_styles import role_value,font_for
            background=role_value(appearance,Qt.BackgroundRole)
            foreground=role_value(appearance,Qt.ForegroundRole)
            if background is not None:option.backgroundBrush=QBrush(background)
            if foreground is not None:option.palette.setBrush(QPalette.Text,QBrush(foreground))
            option.font=font_for(appearance,option.font);option.fontMetrics=QFontMetrics(option.font)
            alignment=role_value(appearance,Qt.TextAlignmentRole)
            if alignment is not None:option.displayAlignment=alignment
            if selected and (background is not None or foreground is not None):
                if background is None:option.backgroundBrush=option.palette.brush(QPalette.Highlight)
                if foreground is None:option.palette.setBrush(QPalette.Text,option.palette.brush(QPalette.HighlightedText))
                option.state &= ~QStyle.State_Selected
        node = index.model().node(index)
        cell_note = node.cell_notes.get(index.column() - 1) if index.column() > 0 else None
        if cell_note is not None and not node.group and not node.footer:
            # A cell note is green: it marks one value, the yellow row note marks the line.
            color = QColor("#2f5138" if index.model().dark else "#d8f0d0")
            option.backgroundBrush = QBrush(color)
            option.palette.setColor(QPalette.Text, contrast_color(color))
            if selected:
                option.palette.setBrush(QPalette.Highlight, QBrush(color))
                option.palette.setColor(QPalette.HighlightedText, contrast_color(color))
        if node.note is not None and not node.group and not node.footer:
            color = QColor("#665c27" if index.model().dark else "#fff4c2")
            option.backgroundBrush = QBrush(color)
            option.palette.setColor(QPalette.Text, contrast_color(color))
            # Keep a uniform marked row even when individual cells have rules.
            if selected:
                option.palette.setBrush(QPalette.Highlight, QBrush(color))
                option.palette.setColor(QPalette.HighlightedText, contrast_color(color))
        # Transparent fills are drawn over the actual alternating row base.
        # Compute automatic text contrast there, rather than against white or
        # the RGB channels of the translucent color alone.
        if not option.state & QStyle.State_Selected and 'foreground' not in merge_styles(*layers):
            from PySide6.QtWidgets import QStyleOptionViewItem
            brush=option.backgroundBrush
            if brush.style()!=Qt.NoBrush:
                background=brush.gradient().stops()[0][1] if brush.gradient() else brush.color()
                base=option.palette.color(QPalette.AlternateBase if option.features & QStyleOptionViewItem.Alternate else QPalette.Base)
                option.palette.setColor(QPalette.Text,contrast_color(background,base))

    def state_layers(self,index,option):
        if index.model().node(index).footer:return []
        styles=index.model().view.layout_styles
        result=[]
        if option.state & QStyle.State_Selected:result.append(styles.get('selected_row',{}))
        widget=self.parent();current=widget.currentIndex() if hasattr(widget,'currentIndex') else QModelIndex()
        if current.isValid() and current.row()==index.row() and current.parent()==index.parent():result.append(styles.get('focused_row',{}))
        if option.state & QStyle.State_HasFocus:result.append(styles.get('focused_cell',{}))
        return result

    def appearance_layers(self,index,option):
        return index.model().appearance_layers(index)+self.state_layers(index,option)

    def appearance(self,index,option):
        from fireblade.ui.layout_styles import merge_styles
        return merge_styles(*self.appearance_layers(index,option))

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        view=index.model().view;node=index.model().node(index)
        parent=self.parent();owner=getattr(parent,'_pinned_tree',parent)
        if view.auto_row_height and hasattr(owner,'row_heights'):
            size.setHeight(owner.row_heights.height(index))
        else:
            fixed=view.group_row_height if node.group and not node.footer and view.group_row_height else view.row_height
            size.setHeight(fixed or max(22,option.fontMetrics.height()+6,getattr(index.model(),'max_rule_height',0)))
        return size

    def paint(self, painter, option, index):
        from PySide6.QtWidgets import QStyleOptionViewItem,QApplication
        from fireblade.ui.layout_styles import paint_image,paint_border,paint_text
        appearance=self.appearance(index,option)
        custom=any(key in appearance for key in ('image','word_wrap','trimming','hotkey'))
        if custom:
            prepared=QStyleOptionViewItem(option);self.initStyleOption(prepared,index)
            label=prepared.text;prepared.text=''
            widget=prepared.widget or self.parent()
            qtstyle=widget.style() if widget else QApplication.style()
            qtstyle.drawControl(QStyle.CE_ItemViewItem,prepared,painter,widget)
            painter.save();painter.setClipRect(option.rect)
            paint_image(painter,option.rect.adjusted(2,2,-2,-2),appearance)
            painter.setFont(prepared.font)
            painter.setPen(prepared.palette.color(QPalette.HighlightedText if prepared.state & QStyle.State_Selected else QPalette.Text))
            content=qtstyle.subElementRect(QStyle.SE_ItemViewItemText,prepared,widget).adjusted(2,0,-2,0)
            paint_text(painter,content,label,appearance,prepared.displayAlignment)
            painter.restore()
        else:
            from fireblade.ui.text_matches import match_ranges, paint_matches
            view = index.model().view
            terms = [view.highlight, view.search]
            text = str(index.data(Qt.DisplayRole) or '')
            if index.column() > 0 and not index.model().node(index).group and match_ranges(text, terms):
                prepared = QStyleOptionViewItem(option);self.initStyleOption(prepared,index)
                prepared.text = ''
                widget = prepared.widget or self.parent()
                style = widget.style() if widget else QApplication.style()
                style.drawControl(QStyle.CE_ItemViewItem, prepared, painter, widget)
                rect = style.subElementRect(QStyle.SE_ItemViewItemText, prepared, widget).adjusted(2, 0, -2, 0)
                foreground = prepared.palette.color(QPalette.HighlightedText if prepared.state & QStyle.State_Selected else QPalette.Text)
                paint_matches(painter, rect, text, prepared.font, foreground, prepared.displayAlignment, terms)
            else:super().paint(painter, option, index)
        painter.save()
        graphic = index.data(VISUAL_ROLE)
        if graphic:
            mode, fraction, color = graphic
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.setClipRect(option.rect)
            if mode == 'bar':
                bar=index.data(BAR_ROLE)
                axis=bar[0] if bar else 0
                width=option.rect.width()-4;left=option.rect.left()+2
                a,b=round(left+width*axis),round(left+width*fraction)
                painter.drawRect(min(a,b),option.rect.bottom()-4,abs(b-a),3)
                if bar and bar[1]:painter.setPen(QColor(bar[2]));painter.drawLine(a,option.rect.bottom()-6,a,option.rect.bottom()-1)
            elif mode == 'icon':
                settings=index.data(ICON_ROLE)
                level=settings[2] if settings else min(2,int(fraction*3));side=min(16,option.rect.height()-4)
                box=QRect(option.rect.right()-side-2,option.rect.center().y()-side//2,side,side)
                image=icon_image(settings[1]) if settings and settings[1] else None
                if image is not None and not image.isNull():painter.drawImage(box,image)
                elif settings and settings[0]=='arrows':
                    d=max(2,side//2-1);shaft=max(1,d//3)
                    painter.save();painter.translate(box.center());painter.rotate(180-180*level/(settings[3]-1))
                    painter.drawPolygon(QPolygon([QPoint(0,-d),QPoint(d,0),QPoint(shaft,0),QPoint(shaft,d),QPoint(-shaft,d),QPoint(-shaft,0),QPoint(-d,0)]));painter.restore()
                elif settings and settings[0]=='signs':
                    symbols={3:('−','!','+'),4:('−−','−','+','++'),5:('−−','−','0','+','++')}
                    painter.setPen(color);painter.drawText(box,Qt.AlignCenter,symbols[settings[3]][level])
                elif settings and settings[0] in ('triangles','squares','diamonds','stars','ratings','flags'):
                    from fireblade.ui.icon_shapes import paint_shape
                    paint_shape(painter,box,settings[0],level,settings[3],color)
                else:painter.drawEllipse(box.adjusted(3,3,-3,-3))
        painter.setPen(QColor("#e5e5e5"))
        painter.drawLine(option.rect.topRight(), option.rect.bottomRight())
        painter.setPen(QColor("#eeeeee"))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        paint_border(painter,option.rect,appearance)
        painter.restore()


@dataclass(eq=False, slots=True)
class Node:
    parent: Node | None = None
    path: tuple = ()
    values: tuple = ()
    group: bool = True
    children: list = field(default_factory=list)
    more: bool = True
    loading: bool = False
    offset: int = 0
    revision: int = 0
    job: Job | None = None
    styles: tuple = ()
    note: str | None = None
    cell_notes: dict = field(default_factory=dict)   # column -> note
    used: int = 0
    footer: bool = False
    window_size: int = 0
    height: int = 0
    height_key: tuple = ()


class GridModel(QAbstractItemModel):
    status = Signal(str)
    error = Signal(str)
    loaded = Signal()
    memory_evicted = Signal(QModelIndex)
    bookmark_requested = Signal(int, bool)

    def __init__(self, case, pool, parent=None):
        super().__init__(parent)
        self.case, self.pool = case, pool
        self.headers = tuple(case.headers)
        self.settings = case.settings
        self.view = View()
        self.root = Node()
        self.generation = 0
        self._cache_clock = 0
        self.jobs = set()
        self.global_rules = []
        self.rules = []
        self.dark = False
        self.date_format = "source"
        self.date_pattern = "yyyy-MM-dd HH:mm:ss.fffffffK"

    @property
    def notes(self):
        """Compatibility view of the currently loaded notes, never the whole DB."""
        notes, pending = {}, [self.root]
        while pending:
            node = pending.pop()
            pending.extend(node.children)
            if not node.group and node.note is not None:
                notes[node.values[0]] = node.note
        return notes

    @property
    def cell_notes(self):
        """{(row_id, column): note} for the cells of the loaded nodes."""
        notes, pending = {}, [self.root]
        while pending:
            node = pending.pop()
            pending.extend(node.children)
            if not node.group and not node.footer:
                for column, note in node.cell_notes.items():
                    notes[(node.values[0], column)] = note
        return notes

    def update_cell_note(self, row_id, column, note):
        pending = [self.root]
        while pending:
            parent = pending.pop()
            pending.extend(parent.children)
            for row, node in enumerate(parent.children):
                if not node.group and not node.footer and node.values[0] == row_id:
                    if note is None:
                        node.cell_notes.pop(column, None)
                    else:
                        node.cell_notes[column] = note
                    index = self.createIndex(row, column + 1, node)
                    self.dataChanged.emit(index, index)

    def update_bookmark(self, row_id, note):
        """Repaint loaded occurrences without losing selection or open groups."""
        pending=[self.root]
        while pending:
            parent=pending.pop();pending.extend(parent.children)
            for row,node in enumerate(parent.children):
                if not node.group and not node.footer and node.values[0]==row_id:
                    node.note=note
                    self.dataChanged.emit(self.createIndex(row,0,node),self.createIndex(row,len(self.headers),node))

    def reset(self, view, global_rules=()):
        self.case.validate_view(view)
        validate_format_rules(global_rules, self.case.expression_column, self.case.numeric_expression)
        self.beginResetModel()
        self.generation += 1
        for job in self.jobs:
            job.cancel()
        self.case._visual_query_revision=getattr(self.case,"_visual_query_revision",0)+1
        self.view, self.root = copy.deepcopy(view), Node()
        self.global_rules = copy.deepcopy(list(global_rules)) if view.global_rules_enabled else []
        self.rules = self.view.format_rules + self.global_rules
        self.max_rule_height=0
        for rule in self.rules:
            if rule.enabled and rule.use_font and rule.font_size:
                font=QFont(rule.font_family) if rule.font_family else QFont()
                font.setPointSizeF(rule.font_size)
                self.max_rule_height=max(self.max_rule_height,QFontMetrics(font).height()+6)
        from fireblade.ui.layout_styles import font_for
        self.max_header_height=self.view.header_height
        for target,style in self.view.layout_styles.items():
            if target=='header' or target.startswith('header:'):
                self.max_header_height=max(self.max_header_height,QFontMetrics(font_for(style)).height()+8)
            elif style.get('font_size') and (target in ('row','odd_row','even_row','group_row','group_footer','selected_row','focused_row','focused_cell') or target.startswith('cell:')):
                self.max_rule_height=max(self.max_rule_height,QFontMetrics(font_for(style)).height()+6)
        # Uniform bounded height keeps frozen panels aligned and avoids measuring millions of rows.
        all_styles=list(self.view.layout_styles.items())+[("rule",r.appearance) for r in self.rules if r.enabled]
        for target,style in all_styles:
            height=QFontMetrics(font_for(style)).height()*3+8 if style.get('word_wrap') and not self.view.auto_row_height else 0
            if target=='header' or target.startswith('header:'):self.max_header_height=max(self.max_header_height,height)
            elif target in ('row','odd_row','even_row','focused_row','focused_cell','selected_row','group_row','group_footer','rule') or target.startswith('cell:'):self.max_rule_height=max(self.max_rule_height,height)
        self.endResetModel()
        self.fetchMore(QModelIndex())

    def node(self, index):
        return index.internalPointer() if index.isValid() else self.root

    def attached(self, node):
        """Ignore late results for groups removed by paging or collapse."""
        while node is not self.root:
            if node.parent is None or node not in node.parent.children:
                return False
            node = node.parent
        return True

    def cancel_branch(self, node):
        if node.job:
            node.job.cancel()
        for child in node.children:
            self.cancel_branch(child)

    def unload(self, index):
        """Collapsing a group releases its cached descendants."""
        node = self.node(index)
        if not index.isValid() or not node.group or node.footer:
            return
        self.cancel_branch(node)
        node.revision += 1
        node.loading, node.more, node.offset = False, True, 0
        if node.children:
            self.beginRemoveRows(index, 0, len(node.children) - 1)
            node.children.clear()
            self.endRemoveRows()

    def trim_cache(self, target, extra):
        """Bound manual expansion too; retain the branch being navigated.

        The root window and a page per level remain available. Least recently
        fetched sibling branches can be reopened; evidence stays on disk.
        """
        if self.view.expand_all:return
        protected={self.root};ancestor=target
        while ancestor is not None:
            protected.add(ancestor);ancestor=ancestor.parent
        pending=list(self.root.children);total=0;candidates=[]
        while pending:
            node=pending.pop();total+=1;pending.extend(node.children)
            if node.group and node.children and node not in protected:candidates.append(node)
        limit=max(self.settings.max_loaded_rows,len(self.root.children)+self.settings.page_size*(len(self.view.groups)+1))
        def descendants(node):
            count=0;pending=list(node.children)
            while pending:
                child=pending.pop();count+=1;pending.extend(child.children)
            return count
        for node in sorted(candidates,key=lambda n:n.used):
            if total+extra<=limit:break
            if not self.attached(node) or not node.children:continue
            removed=descendants(node)
            index=self.createIndex(node.parent.children.index(node),0,node)
            self.unload(index)
            self.memory_evicted.emit(index)
            total-=removed

    def index(self, row, column, parent=QModelIndex()):
        node = self.node(parent)
        if row < 0 or row >= len(node.children) or column < 0 or column >= self.columnCount():
            return QModelIndex()
        return self.createIndex(row, column, node.children[row])

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        p = self.node(index).parent
        if p is None or p is self.root:
            return QModelIndex()
        return self.createIndex(p.parent.children.index(p), 0, p)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.column() > 0 else len(self.node(parent).children)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers) + 1

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            from fireblade.core.i18n import translate
            return translate("Ligne / groupe") if section == 0 else translate(self.headers[section - 1]) if 0<section<=len(self.headers) else None
        if orientation==Qt.Horizontal:
            from fireblade.ui.layout_styles import role_value,merge_styles
            style=merge_styles(self.view.layout_styles.get('header',{}),self.view.layout_styles.get(f'header:{section-1}',{}))
            return role_value(style,role)

    def cell_rules(self,node,col):
        for i in node.styles:
            rule=self.rules[i]
            if rule.target is None or col==rule.target+1:
                yield rule
                if rule.stop_if_true:break

    def appearance_layers(self,index):
        from fireblade.ui.layout_styles import cell_layers,rule_style
        node=self.node(index)
        layers=cell_layers(self.view,node,index.column(),index.row())
        if not node.group:
            # Rule matches are prepared by the paged query, never queried in paint.
            layers += [rule_style(rule) for rule in reversed(list(self.cell_rules(node,index.column())))]
        return layers

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        node, col = self.node(index), index.column()
        if node.footer:
            from fireblade.ui.layout_styles import role_value
            style=self.view.layout_styles.get('group_footer',{})
            if role==Qt.DisplayRole:
                if col==0:
                    label=self.headers[self.view.groups[len(node.path)-1]]
                    value='∅' if node.path[-1] is None else str(node.path[-1])[:600]
                    indent='    '*(len(node.path)-1) if self.view.expand_all else ''
                    return f'{indent}Total {label} : {value}  ({node.values[1]:,})'[:600]
                values=[]
                for summary,value in zip(self.view.summaries,node.values[2:]):
                    if summary.footer_column==-1:continue
                    target=summary.footer_column if summary.footer_column is not None else summary.column
                    if target==col-1:values.append(f"{summary.operation}={'∅' if value is None else str(value)[:600]}")
                return ' · '.join(values)[:600]
            if role==Qt.ToolTipRole:return self.data(index,Qt.DisplayRole)[:4000]
            styled=role_value(style,role)
            if styled is not None:return styled
            if role==Qt.BackgroundRole:return QColor('#303943' if self.dark else '#f0f3f7')
            if role==Qt.ForegroundRole:return QColor('#eeeeee' if self.dark else '#202020')
            return None
        if role == Qt.DisplayRole:
            if node.group:
                if col:
                    return ""
                label = self.case.headers[self.view.groups[len(node.path) - 1]]
                value, count = node.values[:2]
                result = f"{label} : {'∅' if value is None else str(value)[:600]}  ({count:,})"
                inline=[f"{s.operation}({self.case.headers[s.column]})={'∅' if value is None else str(value)[:600]}" for s,value in zip(self.view.summaries,node.values[2:]) if s.footer_column==-1]
                if inline:result+=' · '+' · '.join(inline)
                return ((("    " * (len(node.path)-1) + "▾ ") if self.view.expand_all else "") + result)[:600]
            if col == 0:
                return ("★ " if node.note is not None else "") + str(node.values[0])
            for rule in self.cell_rules(node,col):
                if rule.visual!='none' and not rule.show_values:return ''
            value = node.values[col]
            if col - 1 in self.view.timestamp_columns and value is not None:
                from fireblade.core.timestamps import display_timestamp
                if self.date_format=='custom':
                    from fireblade.core.timestamps import format_timestamp
                    value = format_timestamp(str(value),self.date_pattern)
                else:
                    value = display_timestamp(str(value), self.date_format)
            if col - 1 in self.view.boolean_columns and str(value).casefold() in ("true", "false", "0", "1"):
                return ""
            if value is None:return '∅'
            if self.view.auto_row_height:
                from fireblade.ui.layout_styles import merge_styles
                if merge_styles(*self.appearance_layers(index)).get('word_wrap'):return str(value)[:600]
            return str(value).replace("\n", " ↵ ")[:600]
        if role == Qt.CheckStateRole and not node.group and col == 0:
            return Qt.Checked if node.note is not None else Qt.Unchecked
        if role == Qt.CheckStateRole and not node.group and col > 0 and col - 1 in self.view.boolean_columns:
            value = str(node.values[col]).casefold()
            if value in ("true", "false", "0", "1"):
                return Qt.Checked if value in ("true", "1") else Qt.Unchecked
        if role == Qt.ToolTipRole and not node.group:
            if col == 0:
                return "Clic : surligner / retirer le signet de toute la ligne.\n" + (node.note or "")
            note = node.cell_notes.get(col - 1)
            return (note + "\n" if note else "") + str(node.values[col])[:4000]
        if node.group:
            from fireblade.ui.layout_styles import role_value
            styled=role_value(self.view.layout_styles.get('group_row',{}),role)
            if styled is not None:return styled
        if role == Qt.ForegroundRole and node.group:
            return QColor("#eeeeee" if self.dark else "#202020")
        if role == Qt.BackgroundRole and node.group:
            return QColor("#39434f" if self.dark else "#e9edf2")
        if not node.group and node.note is not None:
            if role == Qt.BackgroundRole:return QColor("#665c27" if self.dark else "#fff4c2")
            if role == Qt.ForegroundRole:return contrast_color(QColor("#665c27" if self.dark else "#fff4c2"))
        if not node.group and role in (Qt.BackgroundRole, Qt.ForegroundRole, Qt.FontRole, Qt.TextAlignmentRole):
            from fireblade.ui.layout_styles import merge_styles,role_value
            prioritized=role_value(merge_styles(*self.appearance_layers(index),priority_only=True),role)
            if prioritized is not None:return prioritized
        if not node.group and role in (Qt.BackgroundRole, Qt.ForegroundRole, Qt.FontRole, VISUAL_ROLE, ICON_ROLE, BAR_ROLE, Qt.TextAlignmentRole):
            for rule in self.cell_rules(node,col):
                if rule.visual!='none':
                    value_column=rule.value_column if rule.value_column is not None else rule.target
                    value=node.values[value_column+1]
                    graphic=visual_value(rule,value)
                    if graphic is None:continue
                    scale=rule.visual in ('scale','scale3')
                    if role==BAR_ROLE and rule.visual=='bar':
                        from decimal import Decimal
                        low,high=Decimal(rule.minimum),Decimal(rule.maximum)
                        axis=float(max(Decimal(0),min(Decimal(1),-low/(high-low)))) if low<0 and low<high else 0
                        return axis,rule.draw_axis and low<0,rule.axis_color
                    if role==ICON_ROLE and rule.visual=='icon':
                        level=icon_level(rule,value,graphic[1])
                        return rule.icon_set,rule.icon_images[level],level,len(rule.icon_colors)
                    if role==VISUAL_ROLE and not scale:return graphic
                    if role==Qt.BackgroundRole and scale and rule.use_background:return graphic[2]
                    if role==Qt.ForegroundRole and scale and rule.use_foreground and rule.use_background:return contrast_color(graphic[2])
                else:
                    if role==Qt.BackgroundRole and rule.use_background:
                        from fireblade.ui.layout_styles import role_value
                        return role_value(dict(background=rule.background,**rule.appearance),role)
                    if role==Qt.TextAlignmentRole and rule.appearance:
                        from fireblade.ui.layout_styles import role_value
                        alignment=role_value(rule.appearance,role)
                        if alignment is not None:return alignment
                    if role==Qt.ForegroundRole and rule.use_foreground:return QColor(rule.foreground)
                if role==Qt.FontRole and rule.use_font:
                    font=QFont(rule.font_family) if rule.font_family else QFont()
                    if rule.font_size:font.setPointSizeF(rule.font_size)
                    font.setBold(rule.bold);font.setItalic(rule.italic);font.setUnderline(rule.underline);font.setStrikeOut(rule.strikeout)
                    return font

        if not node.group:
            from fireblade.ui.layout_styles import cell_style,role_value
            styled=role_value(cell_style(self.view,node,col,index.row()),role)
            if styled is not None:return styled
        if role==Qt.ForegroundRole and not node.group:
            background=self.data(index,Qt.BackgroundRole)
            if isinstance(background,QColor):return contrast_color(background)
            if isinstance(background,QBrush) and background.gradient():return contrast_color(background.gradient().stops()[0][1])

    def flags(self, index):
        flags = super().flags(index)
        if index.isValid() and self.node(index).footer:return Qt.ItemIsEnabled
        if index.isValid() and index.column() == 0 and not self.node(index).group:
            flags |= Qt.ItemIsUserCheckable
        return flags

    def setData(self, index, value, role=Qt.EditRole):
        if role == Qt.CheckStateRole and index.isValid() and index.column() == 0 and not self.node(index).group:
            self.bookmark_requested.emit(self.node(index).values[0], value == Qt.Checked or value == Qt.Checked.value)
            return True
        return False

    def hasChildren(self, parent=QModelIndex()):
        return parent.column() <= 0 and self.node(parent).group and not self.node(parent).footer and (not self.view.expand_all or not parent.isValid())

    def canFetchMore(self, parent=QModelIndex()):
        # QTreeView may eagerly call fetchMore during relayout. Paging is explicit
        # (expansion / next-page button) so opening a view never scans all pages.
        return False

    def fetchMore(self, parent=QModelIndex()):
        node, generation = self.node(parent), self.generation
        if parent.column() > 0 or not node.group or node.footer or not node.more or node.loading:
            return
        revision = node.revision
        self._cache_clock += 1
        node.used = self._cache_clock
        node.loading = True
        view=copy.deepcopy(self.view)
        outline=view.expand_all and bool(view.groups)
        path=node.path
        loaded=len(node.children) if outline else sum(not child.footer for child in node.children)
        offset=node.offset+loaded
        global_rules = copy.deepcopy(self.global_rules)
        def read_page():
            from fireblade.core.visual_bounds import resolve_rules
            render_rules=resolve_rules(self.case,view,view.format_rules+global_rules)
            if outline:
                records = self.case.outline_page(view,offset=offset)
                rows = [r['values'] for r in records if not r['group']]
                styles = self.case.page_styles(view,rows,global_rules)
                notes = self.case.bookmarks([r[0] for r in rows])
                cells = self.case.cell_notes([r[0] for r in rows])
                return records,styles,notes,cells,render_rules
            rows = self.case.page(view, path, offset)
            leaves = len(path) >= len(view.groups)
            styles = self.case.page_styles(view, rows, global_rules) if leaves else {}
            notes = self.case.bookmarks([row[0] for row in rows]) if leaves else {}
            cells = self.case.cell_notes([row[0] for row in rows]) if leaves else {}
            return rows, styles, notes, cells, render_rules
        job = Job(read_page)
        node.job = job
        self.jobs.add(job)
        self.status.emit("Lecture sur disque…")

        def release():
            self.jobs.discard(job)
            job.signals.done.disconnect(complete)
            job.signals.error.disconnect(failed)
            job.signals.cancelled.disconnect(was_cancelled)
            if node.job is job:
                node.job = None

        def complete(result):
            rows, styles, notes, cells, render_rules = result
            by_row = {}
            for (row_id, column), note in cells.items():
                by_row.setdefault(row_id, {})[column] = note
            release()
            if generation != self.generation or revision != node.revision or not self.attached(node):
                return
            self.rules=render_rules
            node.loading = False
            node.more = len(rows) == self.settings.page_size
            additions=[]
            groups=len(path)<len(view.groups)
            if outline:
                additions=[Node(node,r['path'],r['values'],r['group'],more=False,
                    styles=styles.get(r['values'][0],()) if not r['group'] else (),
                    note=notes.get(r['values'][0]) if not r['group'] else None,
                    cell_notes=by_row.get(r['values'][0], {}),footer=r.get('footer',False)) for r in rows]
            else:
                for r in rows:
                    child_path=path+(r[0],) if groups else path
                    additions.append(Node(node,child_path,r,groups,more=groups,
                        styles=styles.get(r[0],()),note=notes.get(r[0]) if not groups else None,
                        cell_notes=by_row.get(r[0], {})))
                    if groups and view.group_footer_mode=='always':
                        additions.append(Node(node,child_path,r,True,more=False,footer=True))
                if path and view.group_footer_mode=='expanded' and not node.more:
                    additions.append(Node(node,path,node.values,True,more=False,footer=True))
            if additions:
                # Positions into source queries exclude synthetic footers. The
                # flattened index already includes them in its disk positions.
                if rows and len(node.children)>=self.settings.max_loaded_rows:
                    self.beginRemoveRows(parent,0,len(node.children)-1)
                    node.window_size=loaded
                    node.offset+=loaded
                    for child in node.children:self.cancel_branch(child)
                    node.children.clear()
                    self.endRemoveRows()
                self.trim_cache(node,len(additions))
                start=len(node.children)
                self.beginInsertRows(parent,start,start+len(additions)-1)
                node.children+=additions
                self.endInsertRows()
            self.status.emit(f"{offset + len(rows):,} éléments chargés dans ce niveau")
            self.loaded.emit()

        def failed(message):
            release()
            if generation == self.generation and revision == node.revision and self.attached(node):
                node.loading, node.more = False, False
                self.error.emit(message)

        def was_cancelled():
            release()
            if generation == self.generation and revision == node.revision and self.attached(node):
                node.loading, node.more = False, True
                self.status.emit("Lecture annulée. Vous pouvez réessayer avec Suivant.")
        job.signals.done.connect(complete)
        job.signals.error.connect(failed)
        job.signals.cancelled.connect(was_cancelled)
        self.pool.start(job)

    def previous(self, parent=QModelIndex()):
        node = self.node(parent)
        if self.jobs or node.offset == 0:
            return
        self.beginRemoveRows(parent, 0, len(node.children) - 1)
        for child in node.children:
            self.cancel_branch(child)
        node.children.clear()
        node.offset = max(0, node.offset - (node.window_size or self.settings.max_loaded_rows))
        node.more = True
        self.endRemoveRows()
        self.fetchMore(parent)

