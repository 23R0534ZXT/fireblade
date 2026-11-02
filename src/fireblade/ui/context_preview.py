"""Bounded EVTX preview: no extra open database and no tab per alert."""
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QAbstractItemView, QDockWidget, QHBoxLayout, QLabel,
    QPushButton, QSplitter, QTableView, QTextBrowser, QVBoxLayout, QWidget)


class PreviewModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent);self.headers=[];self.rows=[];self.visible=[]

    def replace(self, headers, rows):
        self.beginResetModel();self.headers=headers;self.rows=rows
        wanted={'relation à l’alerte','timecreated','timestamp','eventid','computer','channel','mapdescription'}
        self.visible=[i for i,h in enumerate(headers) if h.casefold() in wanted]
        self.endResetModel()

    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.rows)
    def columnCount(self,parent=QModelIndex()):return len(self.visible)
    def headerData(self,section,orientation,role=Qt.DisplayRole):
        if role==Qt.DisplayRole and orientation==Qt.Horizontal:return self.headers[self.visible[section]]

    def data(self,index,role=Qt.DisplayRole):
        if not index.isValid():return None
        row=self.rows[index.row()]
        if role in (Qt.DisplayRole,Qt.ToolTipRole):
            value=row[self.visible[index.column()]+1]
            return '∅' if value is None else str(value)[:600 if role==Qt.DisplayRole else 4000]
        if role==Qt.FontRole and row[1]=='Événement de l’alerte':
            font=QFont();font.setBold(True);return font

    def record(self,row):
        return dict(zip(self.headers,self.rows[row][1:])) if 0<=row<len(self.rows) else None


class ContextPreview(QDockWidget):
    def __init__(self, parent):
        super().__init__('Contexte EVTX de l’alerte',parent)
        self.setObjectName('evtx-context-preview')
        self.setAllowedAreas(Qt.LeftDockWidgetArea|Qt.RightDockWidgetArea)
        body=QWidget();layout=QVBoxLayout(body)
        self.summary=QLabel();self.summary.setTextFormat(Qt.PlainText);self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        splitter=QSplitter(Qt.Vertical)
        self.table=QTableView();self.model=PreviewModel(self);self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setWordWrap(False);self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide();splitter.addWidget(self.table)
        self.details=QTextBrowser();splitter.addWidget(self.details)
        splitter.setSizes([320,140]);layout.addWidget(splitter,1)
        self.open_source=QPushButton('Ouvrir l’événement EVTX source')
        self.keep=QPushButton('Conserver ce contexte en onglet')
        layout.addWidget(self.open_source);layout.addWidget(self.keep)
        self.setWidget(body)
        self.table.selectionModel().currentChanged.connect(self.select)

    def display(self,result,headers,rows):
        self.model.replace(headers,rows)
        text=f"{result['rule']} · {result['references']} référence(s), {result['events']} événement(s) · ± {result['minutes']} min."
        text+='\nLes voisins temporels ne sont pas automatiquement suspects.'
        if result.get('truncated'):text+=' Contexte limité.'
        if result.get('notes'):text+='\n'+'\n'.join(result['notes'])
        self.summary.setText(text)
        self.open_source.setEnabled(bool(rows))
        self.details.clear()
        if rows:
            selected=next((i for i,row in enumerate(rows) if row[1]=='Événement de l’alerte'),0)
            self.table.setCurrentIndex(self.model.index(selected,0))
        for column in range(self.model.columnCount()):self.table.setColumnWidth(column,180 if column==0 else 130)

    def selected(self):return self.model.record(self.table.currentIndex().row())

    def select(self,current,*_):
        row=self.model.record(current.row()) if current.isValid() else None
        self.open_source.setEnabled(row is not None)
        self.details.setPlainText('\n\n'.join(h+'\n'+('∅' if v is None else str(v)) for h,v in row.items()) if row else '')
