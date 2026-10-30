"""Paged Qt model; no dialogs or window controls."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QStyledItemDelegate

from .models import View
from .workers import Job


class GridDelegate(QStyledItemDelegate):
    """Draw grid lines without a stylesheet that overrides model colors."""
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(21)
        return size

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        painter.save()
        painter.setPen(QColor("#e5e5e5"))
        painter.drawLine(option.rect.topRight(), option.rect.bottomRight())
        painter.setPen(QColor("#eeeeee"))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
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


class GridModel(QAbstractItemModel):
    status = Signal(str)
    error = Signal(str)
    loaded = Signal()

    def __init__(self, case, pool, parent=None):
        super().__init__(parent)
        self.case, self.pool = case, pool
        self.settings = case.settings
        self.view = View()
        self.root = Node()
        self.generation = 0
        self.jobs = set()
        self.notes = case.bookmarks()

    def reset(self, view):
        self.case.validate_view(view)
        self.beginResetModel()
        self.generation += 1
        for job in self.jobs:
            job.cancel()
        self.view, self.root = copy.deepcopy(view), Node()
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
        if not index.isValid() or not node.group:
            return
        self.cancel_branch(node)
        node.revision += 1
        node.loading, node.more, node.offset = False, True, 0
        if node.children:
            self.beginRemoveRows(index, 0, len(node.children) - 1)
            node.children.clear()
            self.endRemoveRows()

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
        return len(self.case.headers) + 1

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return "Ligne / groupe" if section == 0 else self.case.headers[section - 1]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        node, col = self.node(index), index.column()
        if role == Qt.DisplayRole:
            if node.group:
                if col:
                    return ""
                label = self.case.headers[self.view.groups[len(node.path) - 1]]
                value, count = node.values
                return f"{label} : {'∅' if value is None else value}  ({count:,})"
            if col == 0:
                return ("★ " if node.values[0] in self.notes else "") + str(node.values[0])
            value = node.values[col]
            return "∅" if value is None else str(value).replace("\n", " ↵ ")[:600]
        if role == Qt.ToolTipRole and not node.group:
            return self.notes.get(node.values[0], "") if col == 0 else str(node.values[col])[:4000]
        if role == Qt.ForegroundRole and node.group:
            return QColor("#202020")
        if role == Qt.BackgroundRole and node.group:
            return QColor("#e9edf2")
        if not node.group and role in (Qt.BackgroundRole, Qt.ForegroundRole, Qt.FontRole):
            for rule_index in node.styles:
                rule = self.view.format_rules[rule_index]
                if rule.target is None or col == rule.target + 1:
                    if role == Qt.BackgroundRole:
                        return QColor(rule.background)
                    if role == Qt.ForegroundRole:
                        return QColor(rule.foreground)
                    font = QFont()
                    font.setBold(rule.bold)
                    return font
        if role == Qt.BackgroundRole and not node.group and node.values[0] in self.notes:
            return QColor("#fff4c2")
        if role == Qt.BackgroundRole and not node.group and self.view.highlight:
            if any(self.view.highlight.casefold() in str(v).casefold() for v in node.values[1:] if v is not None):
                return QColor("#fce2e2")

    def hasChildren(self, parent=QModelIndex()):
        return parent.column() <= 0 and self.node(parent).group

    def canFetchMore(self, parent=QModelIndex()):
        # QTreeView may eagerly call fetchMore during relayout. Paging is explicit
        # (expansion / next-page button) so opening a view never scans all pages.
        return False

    def fetchMore(self, parent=QModelIndex()):
        node, generation = self.node(parent), self.generation
        if parent.column() > 0 or not node.group or not node.more or node.loading:
            return
        revision = node.revision
        node.loading = True
        view, path, offset = copy.deepcopy(self.view), node.path, node.offset + len(node.children)
        def read_page():
            rows = self.case.page(view, path, offset)
            styles = self.case.page_styles(view, rows) if len(path) >= len(view.groups) else {}
            return rows, styles
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
            rows, styles = result
            release()
            if generation != self.generation or revision != node.revision or not self.attached(node):
                return
            node.loading = False
            node.more = len(rows) == self.settings.page_size
            if rows:
                groups = len(path) < len(view.groups)
                # Bound both rows and groups; release descendants of evicted groups.
                if len(node.children) >= self.settings.max_loaded_rows:
                    self.beginRemoveRows(parent, 0, len(node.children) - 1)
                    node.offset += len(node.children)
                    for child in node.children:
                        self.cancel_branch(child)
                    node.children.clear()
                    self.endRemoveRows()
                start = len(node.children)
                self.beginInsertRows(parent, start, start + len(rows) - 1)
                node.children += [Node(node, path + (r[0],) if groups else path,
                                       r, groups, more=groups, styles=styles.get(r[0], ())) for r in rows]
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
        node.offset = max(0, node.offset - self.settings.max_loaded_rows)
        node.more = True
        self.endRemoveRows()
        self.fetchMore(parent)

