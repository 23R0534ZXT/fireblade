"""Optional analysis controls, kept out of the startup flow."""
import copy

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QDialog,
    QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QTableWidget,QTabWidget,QWidget,QVBoxLayout)
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
        self.headers = headers
        self.footer_mode=QComboBox()
        for label,mode in [('Masqués','hidden'),('Groupes dépliés','expanded'),('Toujours visibles','always')]:self.footer_mode.addItem(label,mode)
        self.footer_mode.setCurrentIndex(self.footer_mode.findData(view.group_footer_mode))
        self.show_total=QCheckBox('Afficher les résumés globaux')
        self.show_total.setChecked(view.show_total_footer)
        tabs=QTabWidget()
        group_tab=QWidget();group_tab.setLayout(QVBoxLayout())
        group_tab.layout().addWidget(self.footer_mode)
        self.table=QTableWidget(0,4)
        self.table.setHorizontalHeaderLabels(['Colonne','Calcul','Type','Colonne du pied'])
        self.table.horizontalHeader().setStretchLastSection(True)
        group_tab.layout().addWidget(self.table)
        group_buttons=QHBoxLayout()
        add,remove=QPushButton('Ajouter un résumé'),QPushButton('Retirer')
        add.clicked.connect(lambda:self.add());remove.clicked.connect(lambda:self.table.removeRow(self.table.currentRow()))
        group_buttons.addWidget(add);group_buttons.addWidget(remove);group_tab.layout().addLayout(group_buttons)
        tabs.addTab(group_tab,'Par groupe')
        total_tab=QWidget();total_tab.setLayout(QVBoxLayout());total_tab.layout().addWidget(self.show_total)
        self.total_table=QTableWidget(0,3)
        self.total_table.setHorizontalHeaderLabels(['Colonne','Calcul','Type']);self.total_table.horizontalHeader().setStretchLastSection(True)
        total_tab.layout().addWidget(self.total_table)
        total_buttons=QHBoxLayout();add_total,remove_total=QPushButton('Ajouter un résumé global'),QPushButton('Retirer')
        add_total.clicked.connect(lambda:self.add(table=self.total_table));remove_total.clicked.connect(lambda:self.total_table.removeRow(self.total_table.currentRow()))
        total_buttons.addWidget(add_total);total_buttons.addWidget(remove_total);total_tab.layout().addLayout(total_buttons)
        tabs.addTab(total_tab,'Pied global');form.addRow(tabs)
        for summary in view.summaries:self.add(summary)
        for summary in view.total_summaries:self.add(summary,self.total_table)
        self.message = QLabel()
        form.addRow(self.message)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def add(self, summary=None,table=None):
        table=self.table if table is None else table
        if table.rowCount() >= 16:
            return
        summary = summary or Summary(0)
        row = table.rowCount()
        table.insertRow(row)
        combos = [QComboBox(), QComboBox(), QComboBox()]
        combos[0].addItems(self.headers)
        combos[0].setCurrentIndex(summary.column)
        for label, value in [("Lignes", "rows"), ("Non vides", "count"), ("Valeurs distinctes", "distinct"), ("Somme", "sum"), ("Moyenne", "avg"), ("Minimum", "min"), ("Maximum", "max")]:
            combos[1].addItem(label, value)
        combos[1].setCurrentIndex(combos[1].findData(summary.operation))
        for label, value in [("Nombre", "number"), ("Texte", "text"), ("Date ISO", "timestamp")]:
            combos[2].addItem(label, value)
        combos[2].setCurrentIndex(combos[2].findData(summary.kind))
        if table.columnCount()==4:
            footer=QComboBox();footer.addItem('Dans l’en-tête du groupe',-1);footer.addItem('Colonne de valeurs',None)
            for index,header in enumerate(self.headers):footer.addItem(header,index)
            footer.setCurrentIndex(footer.findData(summary.footer_column));combos.append(footer)
        for col, combo in enumerate(combos):
            table.setCellWidget(row, col, combo)

    def accept(self):
        def read(table):
            return [Summary(table.cellWidget(i,0).currentIndex(),table.cellWidget(i,1).currentData(),table.cellWidget(i,2).currentData(),
                table.cellWidget(i,3).currentData() if table.columnCount()==4 else -1) for i in range(table.rowCount())]
        summaries=read(self.table)
        totals=read(self.total_table)
        if self.order.currentData() == "summary" and self.selected_summary.value() > len(summaries):
            self.message.setText("Ajoutez ou choisissez un résumé existant.")
            return
        if any(s.operation in ("sum", "avg") and s.kind != "number" for s in summaries+totals):
            self.message.setText("Somme et moyenne nécessitent le type Nombre.")
            return
        if [(s.column,s.operation,s.kind) for s in summaries]!=[(s.column,s.operation,s.kind) for s in self.view.summaries] or (self.order.currentData(),self.descending.isChecked(),self.selected_summary.value()-1)!=(self.view.group_order,self.view.group_descending,self.view.group_summary):
            self.view.group_sorts=[]
        self.view.summaries = summaries
        self.view.total_summaries = totals
        self.view.group_footer_mode=self.footer_mode.currentData()
        self.view.show_total_footer=self.show_total.isChecked()
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
