"""Filterable collection outcome table, with complete diagnostics on demand."""
from collections import Counter
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSplitter, QTableView, QTextBrowser, QVBoxLayout, QWidget)

STATUSES = {'pending':'En attente', 'running':'En cours', 'complete':'Terminé',
    'complete_with_warnings':'Terminé avec avertissements', 'unsupported':'Non reconnu',
    'skipped':'Ignoré', 'error':'Erreur', 'cancelled':'Interrompu', 'attention':'À vérifier',
    'no_output':'Aucune sortie', 'companion':'Journal de transaction'}


class OutcomeModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent);self.entries=[]

    def rowCount(self, parent=QModelIndex()):return 0 if parent.isValid() else len(self.entries)
    def columnCount(self, parent=QModelIndex()):return 4

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation==Qt.Horizontal and role==Qt.DisplayRole:
            return ['État','Fichier','Lecteurs','Sorties'][section]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():return None
        entry=self.entries[index.row()]
        if role==Qt.ToolTipRole:return str(entry.get('path',''))
        if role==Qt.DisplayRole:
            return [STATUSES.get(entry['status'],entry['status']),str(entry.get('path','')),
                    ', '.join(entry.get('tools',[])),
                    sum(len(run.get('outputs',[])) for run in entry.get('runs',[]))][index.column()]


class OutcomeFilter(QSortFilterProxyModel):
    status='';query=''

    def filterAcceptsRow(self, row, parent):
        entry=self.sourceModel().entries[row]
        state=entry['status']
        states={'warnings':{'complete_with_warnings','attention','no_output'},
                'errors':{'error','cancelled'},'unsupported':{'unsupported','skipped'},
                'complete':{'complete'}}
        if self.status and state not in states[self.status]:return False
        return self.query in (str(entry.get('path',''))+' '+str(entry.get('error',''))+' '+
                              ' '.join(entry.get('tools',[]))).casefold()


class CollectionReport(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._text='';self.report=None
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        self.summary=QLabel();self.summary.setTextFormat(Qt.PlainText);self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        row=QHBoxLayout()
        self.status=QComboBox()
        for label,value in [('Tous les fichiers',''),('Réussis','complete'),('Avertissements / à vérifier','warnings'),
                            ('Erreurs / interrompus','errors'),('Non reconnus / ignorés','unsupported')]:
            self.status.addItem(label,value)
        self.search=QLineEdit();self.search.setPlaceholderText('Chercher un fichier ou un lecteur…');self.search.setClearButtonEnabled(True)
        row.addWidget(self.status);row.addWidget(self.search,1)
        self.open_folder=QPushButton('Ouvrir les résultats')
        self.open_folder.clicked.connect(self.open_results)
        layout.addLayout(row)
        actions=QHBoxLayout();actions.addWidget(self.open_folder)
        complete=QPushButton('Bilan complet');complete.clicked.connect(lambda:self.details.setPlainText(self._text))
        actions.addWidget(complete);actions.addStretch();layout.addLayout(actions)
        self.splitter=QSplitter(Qt.Vertical)
        self.table=QTableView();self.model=OutcomeModel(self)
        self.proxy=OutcomeFilter(self);self.proxy.setSourceModel(self.model)
        self.table.setModel(self.proxy);self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True);self.table.setWordWrap(False)
        self.table.verticalHeader().hide()
        self.table.setColumnWidth(0,190);self.table.setColumnWidth(1,390);self.table.setColumnWidth(2,140)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.details=QTextBrowser();self.details.setOpenExternalLinks(False)
        self.splitter.addWidget(self.table);self.splitter.addWidget(self.details)
        self.splitter.setSizes([380,120]);layout.addWidget(self.splitter,1)
        self.status.currentIndexChanged.connect(self.filter)
        self.search.textChanged.connect(self.filter)
        self.table.selectionModel().currentChanged.connect(self.show_entry)

    def set_report(self, report, text):
        self.report=report;self._text=text
        self.model.beginResetModel();self.model.entries=report.get('files',[]) if report else [];self.model.endResetModel()
        self.open_folder.setEnabled(report is not None)
        if report:
            counts=Counter(e['status'] for e in self.model.entries)
            successes=counts['complete'];warnings=sum(counts[s] for s in ('complete_with_warnings','attention','no_output'))
            errors=counts['error']+counts['cancelled'];other=counts['unsupported']+counts['skipped']
            self.summary.setText(f'{len(self.model.entries)} fichiers · {successes} réussis · {warnings} à vérifier · {errors} erreurs/interrompus · {other} non reconnus/ignorés\n'+
                'Import : '+STATUSES.get(report['status'],report['status'])+' · '+str(len(report.get('documents',[])))+' analyses · Source : '+report['source'])
        else:self.summary.setText('Aucune collecte ouverte. Importez un dossier ou reprenez une collecte existante.')
        self.details.setPlainText('Sélectionnez un fichier pour lire ses avertissements, sa provenance et ses sorties. « Bilan complet » affiche les informations de la collecte.' if report else text)
        self.filter()

    def filter(self, *_):
        self.proxy.status=self.status.currentData();self.proxy.query=self.search.text().strip().casefold()
        self.proxy.invalidate()

    def show_entry(self, current, *_):
        if not current.isValid():return
        entry=self.model.entries[self.proxy.mapToSource(current).row()]
        lines=[str(entry.get('path','')), 'État : '+STATUSES.get(entry['status'],entry['status'])]
        if entry.get('sha256'):lines+=['SHA-256 : '+entry['sha256']]
        if entry.get('error'):lines+=[entry['error']]
        for run in entry.get('runs',[]):
            lines+=['',run['tool']+' : '+STATUSES.get(run['status'],run['status']),run.get('error','')]
            lines+=run.get('warnings',[])
            for member in run.get('catscale',{}).get('members',[]):
                if member['status'] in ('error','unsupported','skipped'):
                    lines+=[member['status']+' · '+member['path']+' : '+member.get('reason','')]
            for output in run.get('outputs',[]):
                lines+=['Sortie : '+str(output.get('csv',''))]
        self.details.setPlainText('\n'.join(lines))

    def open_results(self):
        if self.report:QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.report['output']))))

    def toPlainText(self):return self._text

    def setPlainText(self, text):
        self._text=text;self.details.setPlainText(text)
