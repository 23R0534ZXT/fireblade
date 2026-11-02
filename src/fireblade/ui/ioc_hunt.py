"""Bulk offline indicator hunting across the open workspace."""
import copy
from pathlib import Path
import tempfile

from PySide6.QtCore import QAbstractTableModel, Qt, Signal
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPlainTextEdit,
    QPushButton,QCheckBox,QSpinBox,QTableView,QFileDialog,QComboBox,QSplitter)
from fireblade.core.ioc_hunt import parse_indicators,read_indicator_file,KINDS
from fireblade.core.ioc_results import hunt,HuntStore,discover_hunts,batch_text
from fireblade.core.workspace_reader import WorkspaceReader
from fireblade.core.models import View,Filter


class Rows(QAbstractTableModel):
    def __init__(self,headers,parent=None):
        super().__init__(parent);self.headers=headers;self.rows=[]
    def rowCount(self,parent=None):return len(self.rows)
    def columnCount(self,parent=None):return len(self.headers)
    def data(self,index,role=Qt.DisplayRole):
        if index.isValid() and role in (Qt.DisplayRole,Qt.ToolTipRole):return str(self.rows[index.row()][index.column()])
    def headerData(self,section,orientation,role=Qt.DisplayRole):
        if role==Qt.DisplayRole:return self.headers[section] if orientation==Qt.Horizontal else str(section+1)
    def display(self,rows):
        self.beginResetModel();self.rows=rows;self.endResetModel()


class HuntPanel(QWidget):
    progress=Signal(str)
    def __init__(self,window):
        super().__init__();self.window=window;self.store=None;self.reader=None;self.offset=0;self.ioc=None
        self.temporary=tempfile.TemporaryDirectory(prefix='fireblade-ioc-');self.cached=None;self.origin=None;self.hit_rows=[]
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel('Chasse IOC en masse · IP, domaines, URL et empreintes · aucune requête réseau'))
        self.input=QPlainTextEdit();self.input.setPlaceholderText('Un IOC par ligne, ou CSV : type,value,label\n192.0.2.10\nexample.org');self.input.setMaximumHeight(110);layout.addWidget(self.input)
        bar=QHBoxLayout();layout.addLayout(bar)
        self.import_button=QPushButton('Importer TXT / CSV / TSV');bar.addWidget(self.import_button);self.import_button.clicked.connect(self.import_file)
        self.subdomains=QCheckBox('Inclure les sous-domaines');self.subdomains.setChecked(True);bar.addWidget(self.subdomains)
        bar=QHBoxLayout();layout.addLayout(bar)
        self.filters=QCheckBox('Respecter les filtres des analyses');bar.addWidget(self.filters)
        self.limit=QSpinBox();self.limit.setRange(1,5000000);self.limit.setValue(250000);self.limit.setPrefix('Détails max. : ');bar.addWidget(self.limit)
        bar=QHBoxLayout();layout.addLayout(bar)
        self.build_button=QPushButton('Chasser dans toutes les analyses ouvertes');bar.addWidget(self.build_button);self.build_button.clicked.connect(self.launch)
        stop=QPushButton('Interrompre');bar.addWidget(stop);stop.clicked.connect(window.interrupt_queries)
        self.history=QComboBox();bar.addWidget(self.history);self.history.activated.connect(self.load_history)
        refresh=QPushButton('Historique');bar.addWidget(refresh);refresh.clicked.connect(self.refresh_history)
        self.status=QLabel('Collez une liste ou importez un fichier. Hors dossier d’enquête, les résultats sont temporaires.');self.status.setTextFormat(Qt.PlainText);self.status.setWordWrap(True);layout.addWidget(self.status);self.progress.connect(self.status.setText)
        splitter=QSplitter(Qt.Vertical);layout.addWidget(splitter)
        self.indicators=QTableView();self.summary=Rows(['Type','IOC original','Valeur normalisée','Libellé','Champs','Lignes','Détails'],self);self.indicators.setModel(self.summary);self.indicators.setSelectionBehavior(QTableView.SelectRows);splitter.addWidget(self.indicators)
        self.indicators.clicked.connect(self.select_ioc)
        self.results=QTableView();self.model=Rows(['Date source','IOC','Analyse','Ligne source','Colonne','Valeur observée','Extrait','Règle'],self);self.results.setModel(self.model);splitter.addWidget(self.results)
        self.results.doubleClicked.connect(self.open_source)
        self.return_button=QPushButton('Retour à la chasse IOC');self.return_button.clicked.connect(self.return_to_hunt)
        self.return_action=window.main_toolbar.addWidget(self.return_button)
        self.return_action.setVisible(False)
        bar=QHBoxLayout();layout.addLayout(bar)
        for title,callback in [('Tous les IOC',self.all_iocs),('Précédent',lambda:self.page(-250)),('Suivant',lambda:self.page(250)),('Exporter les occurrences',lambda:self.export(False)),('Exporter la synthèse',lambda:self.export(True))]:
            button=QPushButton(title);bar.addWidget(button);button.clicked.connect(callback)
        self.page_label=QLabel();bar.addWidget(self.page_label)
    def root(self):
        data=self.window.active_investigation
        return self.window.investigation_library.folder(data['id'])/'IOC-hunts' if data else Path(self.temporary.name)
    def interrupt(self):
        if self.reader:self.reader.interrupt()
    def reset_workspace(self):
        self.interrupt();self.origin=None;self.return_action.setVisible(False)
        if self.store:self.store.close();self.store=None
        self.summary.display([]);self.model.display([]);self.history.clear();self.input.clear();self.cached=None;self.hit_rows=[];self.offset=0;self.page_label.clear()
        self.status.setText('Nouvelle enquête · aucun résultat de chasse chargé.');self.temporary.cleanup();self.temporary=tempfile.TemporaryDirectory(prefix='fireblade-ioc-')
    def import_file(self):
        if not self.window.can_open_file():return
        path,_=QFileDialog.getOpenFileName(self,'Liste IOC','','Listes IOC (*.txt *.csv *.tsv);;Tous les fichiers (*)')
        if not path:return
        def done(batch):
            text=batch_text(batch);self.input.setPlainText(text);self.cached=(text,batch)
            self.status.setText(f'{len(batch.indicators)} IOC valides · {batch.duplicates} doublons · {len(batch.rejected)} lignes rejetées. '+self.rejections(batch))
        self.window.run(lambda:read_indicator_file(path),done)
    @staticmethod
    def rejections(batch):return ' ; '.join(f"Ligne {r['line']} : {r['reason']}" for r in batch.rejected[:10])
    def launch(self):
        if not self.window.can_open_file():return
        self.restore_origin(refresh=False)
        self.window.remember_active();documents=self.window.documents
        if not documents:self.window.error('Ouvrez au moins une analyse.');return
        text=self.input.toPlainText();cached=self.cached;root=self.root();sub=self.subdomains.isChecked();filters=self.filters.isChecked();limit=self.limit.value()
        self.reader=WorkspaceReader(documents,self.window.settings,self.window.case);reader=self.reader
        self.build_button.setEnabled(False)
        def work():
            batch=cached[1] if cached and cached[0]==text else parse_indicators(text)
            return hunt(reader,batch,root,include_subdomains=sub,respect_filters=filters,hit_limit=limit,progress=self.progress.emit)
        def release():self.reader=None;self.build_button.setEnabled(True)
        def done(store):release();self.display(store)
        def fail(message):release();self.window.error(message)
        def cancel():release();self.status.setText('Chasse annulée. Les résultats précédents sont conservés.')
        self.window.run(work,done,on_cancel=cancel,on_error=fail)
    def display(self,store):
        if self.store and self.store is not store:self.store.close()
        self.store=store;self.ioc=None;self.offset=0
        self.summary.display([[KINDS[r[1]],*r[2:]] for r in store.indicators()]);self.indicators.resizeColumnsToContents()
        m=store.metadata;state={'complete':'Terminée','partial':'Partielle','running':'Inachevée — à relancer'}.get(m.get('status'),'État inconnu');errors=' ; '.join(s['error'] for s in store.sources() if s['error'])
        self.status.setText(f"{state} · {m.get('scanned_rows',0):,} lignes lues · {m.get('matching_fields',0):,} champs correspondants · {m.get('stored_hits',0):,} détails conservés. "
            +('Détails limités : les compteurs portent sur toute la lecture. ' if m.get('truncated') else '')
            +('Périmètre : filtres enregistrés. ' if m.get('respect_filters') else 'Périmètre : toutes les lignes des analyses ouvertes. ')
            +f"{m.get('rejected',0)} IOC rejetés. "+errors+' Une présence est une observation, pas un verdict de compromission.')
        self.refresh_after_page=True;self.page(0)
    def select_ioc(self,index):self.ioc=index.row()+1;self.offset=0;self.page(0)
    def all_iocs(self):self.ioc=None;self.offset=0;self.page(0)
    def page(self,delta):
        if not self.store or not self.window.can_open_file():return
        offset=max(0,self.offset+delta);store=self.store;ioc=self.ioc
        def work():
            actual=offset;data=store.page(actual,ioc=ioc)
            if actual and not data['rows']:
                actual=max(0,((data['count']-1)//250)*250);data=store.page(actual,ioc=ioc)
            return actual,data
        def done(value):
            actual,data=value
            self.hit_rows=data['rows'];self.offset=actual;self.model.display([[r[8],r[12],Path(r[14]).name,r[3],r[5],r[6],r[7],r[9]] for r in data['rows']]);self.page_label.setText(f'{actual+1 if data["count"] else 0}–{actual+len(data["rows"])} / {data["count"]} détails')
            self.results.resizeColumnsToContents()
            if getattr(self,'refresh_after_page',False):
                self.refresh_after_page=False;self.refresh_history()
        self.window.run(work,done)
    def restore_origin(self,refresh=True):
        origin=self.origin
        if origin:
            target=next((i for i,d in enumerate(self.window.documents) if d.path==origin.path and d.source_info==origin.source_info),None)
            if target is not None:
                if self.window.case and str(self.window.case.path)==origin.path:
                    if refresh:self.window.set_view(copy.deepcopy(origin.view))
                    else:self.window.view=copy.deepcopy(origin.view)
                    if origin.header_state:self.window.tree.header().restoreState(origin.header_state)
                self.window.documents[target]=origin
        self.origin=None;self.return_action.setVisible(False)
    def return_to_hunt(self):
        if not self.window.can_open_file():return
        self.restore_origin();self.window.workbench.setCurrentWidget(self)
    def open_source(self,index):
        if not self.window.can_open_file() or not index.isValid():return
        row=self.hit_rows[index.row()]
        import json
        info=json.loads(row[15]);path=row[14]
        target=next((i for i,d in enumerate(self.window.documents) if d.path==path and d.source_info==info),None)
        if target is None:
            self.window.error('Cette analyse est fermée ou a changé. Rouvrez l’analyse d’origine avant de consulter cette ligne.');return
        self.restore_origin(refresh=False);self.window.restore_timeline_origin(refresh=False)
        self.window.switch_document(target)
        if self.window.case and str(self.window.case.path)==path and self.window.case.info==info:
            self.origin=copy.deepcopy(self.window.snapshot_analysis());self.return_action.setVisible(True)
            self.window.set_view(View(filters=[Filter(-1,'eq',str(row[3]))]));self.window.workbench.setCurrentIndex(0)
    def refresh_history(self):
        if not self.window.can_open_file():return
        root=self.root()
        def done(value):
            self.history.clear();self.history.addItem('Chasses enregistrées…',None)
            for item in value[0]:self.history.addItem(item.get('started','')+' · '+item.get('status',''),item['path'])
            if value[1]:self.status.setText(' ; '.join(value[1]))
        self.window.run(lambda:discover_hunts(root),done)
    def load_history(self,index):
        path=self.history.itemData(index)
        if not path or not self.window.can_open_file():return
        self.window.run(lambda:HuntStore(path),self.display)
    def export(self,summary):
        if not self.store or not self.window.can_open_file():return
        path,_=QFileDialog.getSaveFileName(self,'Exporter la chasse','','CSV (*.csv);;Excel (*.xlsx)')
        if not path or not self.window.investigation_destination_is_safe(path):return
        store=self.store;self.window.run(lambda:store.export(path,summary=summary),lambda _:self.window.statusBar().showMessage('Chasse exportée.'))
