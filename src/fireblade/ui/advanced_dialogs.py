"""Ordinary Qt editors for Boolean conditions and ordered formatting rules."""
import copy

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog,
    QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox,
    QPushButton, QTableWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from fireblade.core.models import Filter, FilterGroup, FormatRule, SortKey, OPERATORS


class ExpressionEditor(QWidget):
    def __init__(self, headers, condition=None, parent=None):
        super().__init__(parent)
        self.headers = headers
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Logique / colonne", "Condition", "Valeur"])
        self.tree.setColumnWidth(0, 235)
        self.tree.setColumnWidth(1, 185)
        layout.addWidget(self.tree)
        row = QHBoxLayout()
        for label, callback in [("+ Condition", self.add_condition), ("+ Groupe", self.add_group), ("Retirer", self.remove)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)
        self.root = self.add_node(None, condition or FilterGroup())
        self.tree.setCurrentItem(self.root)
        self.tree.expandAll()

    def add_node(self, parent, value):
        item = QTreeWidgetItem(parent) if parent is not None else QTreeWidgetItem(self.tree)
        is_group = isinstance(value, FilterGroup)
        item.setData(0, Qt.UserRole, is_group)
        choice = QComboBox()
        if is_group:
            for label, logic in [("ET : toutes", "and"), ("OU : au moins une", "or"), ("NON : inverse", "not")]:
                choice.addItem(label, logic)
            choice.setCurrentIndex(choice.findData(value.logic))
        else:
            choice.addItems(self.headers)
            choice.setCurrentIndex(value.column)
        self.tree.setItemWidget(item, 0, choice)
        if is_group:
            for child in value.children:
                self.add_node(item, child)
        else:
            operator = QComboBox()
            for label, code in OPERATORS:
                operator.addItem(label, code)
            operator.setCurrentIndex(operator.findData(value.operator))
            self.tree.setItemWidget(item, 1, operator)
            self.tree.setItemWidget(item, 2, QLineEdit(value.value))
        item.setExpanded(True)
        return item

    def destination(self):
        item = self.tree.currentItem() or self.root
        return item if item.data(0, Qt.UserRole) else item.parent()

    def add_condition(self):
        self.tree.setCurrentItem(self.add_node(self.destination(), Filter(0, "contains")))

    def add_group(self):
        self.tree.setCurrentItem(self.add_node(self.destination(), FilterGroup()))

    def remove(self):
        item = self.tree.currentItem()
        if item and item is not self.root:
            item.parent().removeChild(item)
            self.tree.setCurrentItem(self.root)

    def value(self, item=None, depth=0):
        if depth > 24:
            raise ValueError("24 niveaux au maximum")
        item = self.root if item is None else item
        choice = self.tree.itemWidget(item, 0)
        if item.data(0, Qt.UserRole):
            children = [self.value(item.child(i), depth + 1) for i in range(item.childCount())]
            logic = choice.currentData()
            if logic == "not" and len(children) != 1:
                raise ValueError("Placez une seule condition ou un seul groupe sous NON.")
            return FilterGroup(logic, children)
        return Filter(choice.currentIndex(), self.tree.itemWidget(item, 1).currentData(), self.tree.itemWidget(item, 2).text())


class FilterDialog(QDialog):
    def __init__(self, headers, expression, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Éditeur de filtres · ET / OU / NON")
        self.resize(760, 420)
        layout = QVBoxLayout(self)
        self.editor = ExpressionEditor(headers, expression)
        layout.addWidget(self.editor)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        try:
            self.expression = self.editor.value()
        except ValueError as exc:
            QMessageBox.warning(self, "Condition invalide", str(exc))
            return
        super().accept()


class SortDialog(QDialog):
    def __init__(self, headers, keys, parent=None):
        super().__init__(parent)
        self.headers = headers
        self.setWindowTitle("Tri sur plusieurs colonnes · priorité de haut en bas")
        self.resize(620, 360)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Colonne", "Type", "Ordre"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        row = QHBoxLayout()
        for label, callback in [("Ajouter", lambda: self.add()), ("Retirer", self.remove), ("Monter", lambda: self.move(-1)), ("Descendre", lambda: self.move(1))]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        self.message = QLabel()
        layout.addWidget(self.message)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        for key in keys:
            self.add(key)

    def add(self, key=None):
        if self.table.rowCount() >= 16:
            self.message.setText("16 colonnes de tri au maximum")
            return
        key = key or SortKey(0)
        index = self.table.rowCount()
        self.table.insertRow(index)
        column, kind, order = QComboBox(), QComboBox(), QComboBox()
        column.addItems(self.headers)
        column.setCurrentIndex(key.column)
        for label, value in [("Texte", "text"), ("Nombre", "number"), ("Date ISO", "timestamp")]:
            kind.addItem(label, value)
        kind.setCurrentIndex(kind.findData(key.kind))
        order.addItems(["Croissant", "Décroissant"])
        order.setCurrentIndex(int(key.descending))
        for c, widget in enumerate((column, kind, order)):
            self.table.setCellWidget(index, c, widget)
        self.table.setCurrentCell(index, 0)

    def remove(self):
        if self.table.currentRow() >= 0:
            self.table.removeRow(self.table.currentRow())

    def values(self):
        return [SortKey(self.table.cellWidget(i, 0).currentIndex(), self.table.cellWidget(i, 1).currentData(),
                        bool(self.table.cellWidget(i, 2).currentIndex())) for i in range(self.table.rowCount())]

    def move(self, delta):
        row = self.table.currentRow()
        other = row + delta
        if row < 0 or not 0 <= other < self.table.rowCount():
            return
        keys = self.values()
        keys[row], keys[other] = keys[other], keys[row]
        self.table.setRowCount(0)
        for key in keys:
            self.add(key)
        self.table.setCurrentCell(other, 0)

    def accept(self):
        self.keys = self.values()
        if len({key.column for key in self.keys}) != len(self.keys):
            self.message.setText("Chaque colonne ne doit apparaître qu’une seule fois")
            return
        super().accept()


class RulesDialog(QDialog):
    def __init__(self, headers, rules, parent=None):
        super().__init__(parent)
        self.headers, self.rules = headers, copy.deepcopy(rules)
        self.setWindowTitle("Règles de coloration · première règle correspondante prioritaire")
        self.resize(850, 540)
        self.current = -1
        layout = QVBoxLayout(self)
        self.listing = QListWidget()
        self.listing.setMaximumHeight(115)
        layout.addWidget(self.listing)
        row = QHBoxLayout()
        for label, callback in [("Ajouter", self.add), ("Supprimer", self.remove), ("Monter", lambda: self.move(-1)), ("Descendre", lambda: self.move(1))]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        controls = QHBoxLayout()
        self.enabled = QCheckBox("Active")
        controls.addWidget(self.enabled)
        self.target = QComboBox()
        self.target.addItem("Toute la ligne", None)
        for i, header in enumerate(headers):
            self.target.addItem(header, i)
        controls.addWidget(self.target)
        self.background = QPushButton("Fond")
        self.foreground = QPushButton("Texte")
        self.background.clicked.connect(lambda: self.pick_color(self.background))
        self.foreground.clicked.connect(lambda: self.pick_color(self.foreground))
        controls.addWidget(self.background)
        controls.addWidget(self.foreground)
        self.bold = QCheckBox("Gras")
        controls.addWidget(self.bold)
        layout.addLayout(controls)
        visual_row = QHBoxLayout()
        self.visual = QComboBox()
        for label, code in [('Couleurs / gras', 'none'), ('Barre de données', 'bar'), ('Dégradé fond → texte', 'scale'), ('Indicateur à trois niveaux', 'icon')]:
            self.visual.addItem(label, code)
        self.visual.setToolTip('Les modes graphiques nécessitent une colonne cible. Bornes fixes pour toutes les pages ; les valeurs invalides restent sans graphique. Le dégradé va de la couleur Fond à la couleur Texte ; les indicateurs sont rouge, ambre et vert.')
        self.minimum, self.maximum = QLineEdit('0'), QLineEdit('100')
        visual_row.addWidget(self.visual)
        visual_row.addWidget(QLabel('Minimum'))
        visual_row.addWidget(self.minimum)
        visual_row.addWidget(QLabel('Maximum'))
        visual_row.addWidget(self.maximum)
        layout.addLayout(visual_row)
        self.editor = ExpressionEditor(headers)
        layout.addWidget(self.editor)
        self.message = QLabel()
        layout.addWidget(self.message)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.listing.currentRowChanged.connect(self.select)
        self.refresh(0 if self.rules else -1)

    def pick_color(self, button):
        color = QColorDialog.getColor(QColor(button.property("color") or "#ffffff"), self)
        if color.isValid():
            self.set_color(button, color.name())

    @staticmethod
    def set_color(button, color):
        button.setProperty("color", color)
        button.setStyleSheet(f"border-bottom: 4px solid {color};")

    def store(self):
        if self.current >= 0:
            self.rules[self.current] = FormatRule(self.editor.value(), self.background.property("color"),
                self.foreground.property("color"), self.bold.isChecked(), self.target.currentData(), self.enabled.isChecked(), self.visual.currentData(), self.minimum.text(), self.maximum.text())

    def refresh(self, selected):
        self.listing.blockSignals(True)
        self.listing.clear()
        for i, rule in enumerate(self.rules):
            self.listing.addItem(f"{i + 1}. {'Active' if rule.enabled else 'Inactive'} · {self.headers[rule.target] if rule.target is not None else 'Toute la ligne'}")
        self.listing.setCurrentRow(selected)
        self.listing.blockSignals(False)
        self.current = -1
        self.select(selected)

    def select(self, index):
        try:
            self.store()
        except ValueError as exc:
            self.message.setText(str(exc))
            self.listing.blockSignals(True)
            self.listing.setCurrentRow(self.current)
            self.listing.blockSignals(False)
            return
        self.current = index
        rule = self.rules[index] if index >= 0 else FormatRule()
        self.enabled.setChecked(rule.enabled)
        self.target.setCurrentIndex(self.target.findData(rule.target))
        self.bold.setChecked(rule.bold)
        self.visual.setCurrentIndex(self.visual.findData(rule.visual))
        self.minimum.setText(rule.minimum)
        self.maximum.setText(rule.maximum)
        self.set_color(self.background, rule.background)
        self.set_color(self.foreground, rule.foreground)
        old = self.editor
        # A dialog's nested event loop can defer deleteLater() until it closes.
        # Retire the old controls immediately so they cannot cover or intercept
        # clicks intended for the replacement editor.
        old.hide()
        old.setEnabled(False)
        self.editor = ExpressionEditor(self.headers, rule.condition)
        self.layout().replaceWidget(old, self.editor)
        old.deleteLater()
        for widget in (self.editor, self.enabled, self.target, self.background, self.foreground, self.bold, self.visual, self.minimum, self.maximum):
            widget.setEnabled(index >= 0)
        self.message.clear()

    def add(self):
        try:
            self.store()
            if len(self.rules) >= 32:
                raise ValueError("32 règles au maximum")
        except ValueError as exc:
            self.message.setText(str(exc))
            return
        self.rules.append(FormatRule(FilterGroup("and", [Filter(0, "contains")])))
        self.refresh(len(self.rules) - 1)

    def remove(self):
        if self.current >= 0:
            del self.rules[self.current]
            self.refresh(min(self.current, len(self.rules) - 1))

    def move(self, direction):
        destination = self.current + direction
        if self.current < 0 or not 0 <= destination < len(self.rules):
            return
        try:
            self.store()
        except ValueError as exc:
            self.message.setText(str(exc))
            return
        self.rules[self.current], self.rules[destination] = self.rules[destination], self.rules[self.current]
        self.refresh(destination)

    def accept(self):
        try:
            self.store()
            from fireblade.core.rule_store import RuleBook
            RuleBook(self.headers, self.rules).validate()
        except ValueError as exc:
            self.message.setText(str(exc))
            return
        super().accept()
