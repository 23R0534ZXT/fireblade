"""Optional analysis controls, kept out of the startup flow."""
import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QDialog,
    QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QListWidget, QPushButton,
    QSpinBox, QTableWidget, QVBoxLayout)
from fireblade.core.models import Summary


class GroupsDialog(QDialog):
    def __init__(self, headers, view, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Résumés et tri des groupes")
        self.resize(640, 400)
        self.view = copy.deepcopy(view)
        form = QFormLayout(self)
        self.order = QComboBox()
        for label, code in [("Effectif", "count"), ("Valeur du groupe", "value"), ("Résumé", "summary")]:
            self.order.addItem(label, code)
        self.order.setCurrentIndex(self.order.findData(view.group_order))
        self.descending = QCheckBox("Décroissant")
        self.descending.setChecked(view.group_descending)
        self.selected_summary = QSpinBox()
        self.selected_summary.setRange(1, 16)
        self.selected_summary.setValue(view.group_summary + 1)
        form.addRow("Trier les groupes par", self.order)
        form.addRow(self.descending)
        form.addRow("Numéro du résumé utilisé pour le tri", self.selected_summary)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Colonne", "Calcul", "Type"])
        self.table.horizontalHeader().setStretchLastSection(True)
        form.addRow(self.table)
        self.headers = headers
        for summary in view.summaries:
            self.add(summary)
        buttons_row = QHBoxLayout()
        add, remove = QPushButton("Ajouter un résumé"), QPushButton("Retirer")
        add.clicked.connect(lambda: self.add())
        remove.clicked.connect(lambda: self.table.removeRow(self.table.currentRow()))
        buttons_row.addWidget(add)
        buttons_row.addWidget(remove)
        form.addRow(buttons_row)
        self.message = QLabel()
        form.addRow(self.message)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def add(self, summary=None):
        if self.table.rowCount() >= 16:
            return
        summary = summary or Summary(0)
        row = self.table.rowCount()
        self.table.insertRow(row)
        combos = [QComboBox(), QComboBox(), QComboBox()]
        combos[0].addItems(self.headers)
        combos[0].setCurrentIndex(summary.column)
        for label, value in [("Non vides", "count"), ("Valeurs distinctes", "distinct"), ("Somme", "sum"), ("Moyenne", "avg"), ("Minimum", "min"), ("Maximum", "max")]:
            combos[1].addItem(label, value)
        combos[1].setCurrentIndex(combos[1].findData(summary.operation))
        for label, value in [("Nombre", "number"), ("Texte", "text"), ("Date ISO", "timestamp")]:
            combos[2].addItem(label, value)
        combos[2].setCurrentIndex(combos[2].findData(summary.kind))
        for col, combo in enumerate(combos):
            self.table.setCellWidget(row, col, combo)

    def accept(self):
        summaries = [Summary(self.table.cellWidget(i, 0).currentIndex(),
                            self.table.cellWidget(i, 1).currentData(),
                            self.table.cellWidget(i, 2).currentData()) for i in range(self.table.rowCount())]
        if self.order.currentData() == "summary" and self.selected_summary.value() > len(summaries):
            self.message.setText("Ajoutez ou choisissez un résumé existant.")
            return
        if any(s.operation in ("sum", "avg") and s.kind != "number" for s in summaries):
            self.message.setText("Somme et moyenne nécessitent le type Nombre.")
            return
        self.view.summaries = summaries
        self.view.group_order = self.order.currentData()
        self.view.group_descending = self.descending.isChecked()
        self.view.group_summary = self.selected_summary.value() - 1
        super().accept()


class DateFilterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Filtrer une date")
        form = QFormLayout(self)
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("yyyy-MM-dd")
        from PySide6.QtCore import QDate
        self.date.setDate(QDate.currentDate())
        self.interval = QComboBox()
        for label, code in [("Ce jour", "day"), ("Ce mois", "month"), ("Cette année", "year")]:
            self.interval.addItem(label, code)
        form.addRow("Date", self.date)
        form.addRow("Période", self.interval)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def bounds(self):
        date, interval = self.date.date(), self.interval.currentData()
        if interval == "year":
            date = date.__class__(date.year(), 1, 1)
            end = date.addYears(1)
        elif interval == "month":
            date = date.__class__(date.year(), date.month(), 1)
            end = date.addMonths(1)
        else:
            end = date.addDays(1)
        return date.toString("yyyy-MM-dd"), end.toString("yyyy-MM-dd")
