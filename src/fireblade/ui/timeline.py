"""Interactive density timeline and cross-artifact entity investigation."""
import copy
import json
import math
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QPainter, QPen, QPalette, QPolygonF
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QScrollArea, QFileDialog,
    QSplitter, QStyle, QTableView, QTableWidget, QTableWidgetItem, QTextBrowser, QToolTip, QVBoxLayout, QWidget)

from fireblade.ui.flow_layout import FlowLayout
from fireblade.core.layout import write_json
from fireblade.core.models import Filter, View
from fireblade.core.timeline import KINDS, TimelineStore, field_kind, guess_time_column, utc_label
from fireblade.core.workspace_reader import WorkspaceReader

COLORS = ['#2d9cdb','#e6a23c','#27ae82','#bb6bd9','#eb6577','#56bfc4','#9fa8da','#b4a34a']


class TimelineOverview(QWidget):
    centered = Signal(object)
    def __init__(self):
        super().__init__();self.setFixedHeight(66);self.histogram=None;self.bounds=None
        self.setToolTip('Vue d’ensemble · Cliquez pour déplacer la fenêtre temporelle')
    def display(self,histogram,bounds):self.histogram=histogram;self.bounds=bounds;self.update()
    def paintEvent(self,event):
        painter=QPainter(self);painter.fillRect(self.rect(),self.palette().color(QPalette.Base))
        painter.setPen(self.palette().color(QPalette.PlaceholderText));painter.drawText(12,18,'VUE D’ENSEMBLE')
        data=self.histogram
        if not data:return
        left=TimelineCanvas.LEFT;width=max(1,self.width()-left-24);counts={}
        for _,bucket,count,_ in data['rows']:counts[bucket]=counts.get(bucket,0)+count
        peak=max(counts.values(),default=1)
        for bucket,count in counts.items():
            height=36*math.log1p(count)/math.log1p(peak)
            painter.fillRect(QRectF(left+width*bucket/data['bins'],57-height,max(1,width/data['bins']-1),height),QColor(COLORS[0]))
        if self.bounds:
            span=max(1,data['end']-data['start'])
            x1=left+width*max(0,min(1,(self.bounds[0]-data['start'])/span));x2=left+width*max(0,min(1,(self.bounds[1]-data['start'])/span))
            color=QColor(COLORS[0]);color.setAlpha(45);painter.fillRect(QRectF(x1,22,max(2,x2-x1),37),color)
            painter.setPen(QPen(QColor(COLORS[0]),2));painter.drawRect(QRectF(x1,22,max(2,x2-x1),37))
    def mousePressEvent(self,event):
        if self.histogram and event.position().x()>=TimelineCanvas.LEFT:
            ratio=max(0,min(1,(event.position().x()-TimelineCanvas.LEFT)/max(1,self.width()-TimelineCanvas.LEFT-24)))
            self.centered.emit(self.histogram['start']+int(ratio*(self.histogram['end']-self.histogram['start'])))


class TimelineCanvas(QWidget):
    rangeSelected = Signal(object, object)
    zoomRequested = Signal(float, float)
    sourceSelected = Signal(int)
    LEFT = 190
    TOP = 114
    LANE = 48

    def __init__(self):
        super().__init__();self.setMouseTracking(True);self.setMinimumWidth(520)
        self.histogram = None;self.sources=[];self.drag=None;self.cursor=None;self.selected_time=None;self.selected_source=None
        self.setMinimumHeight(210)
        self.setToolTip('Molette : zoom · Glisser : sélectionner une période · Double-clic : zoomer · Cliquer une piste : isoler son analyse')

    def display(self, histogram, sources):
        self.histogram=histogram;self.sources=sources;self.drag=None
        self.setMinimumHeight(max(290,self.TOP+len(sources)*self.LANE+46));self.update()

    def position_time(self,x):
        data=self.histogram
        if not data:return None
        ratio=max(0.,min(1.,(x-self.LEFT)/max(1,self.width()-self.LEFT-24)))
        return data['start']+int(ratio*max(1,data['end']-data['start']))

    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
        palette=self.palette();painter.fillRect(self.rect(),palette.color(QPalette.Base))
        text=palette.color(QPalette.Text);muted=palette.color(QPalette.PlaceholderText)
        font=QFont(self.font());font.setBold(True);painter.setFont(font);painter.setPen(text)
        painter.drawText(16,26,'ACTIVITÉ CHRONOLOGIQUE')
        if not self.histogram:
            painter.setFont(self.font());painter.setPen(muted)
            painter.drawText(QRectF(20,55,self.width()-40,100),Qt.AlignCenter|Qt.TextWordWrap,
                             'Construisez la chronologie pour explorer vos événements.\nChoisissez les colonnes de date avec « Sources et dates… ».')
            return
        data=self.histogram;left=self.LEFT;width=max(1,self.width()-left-24)
        counts={};global_counts={};marks={}
        for source,bucket,count,marked in data['rows']:
            counts[source,bucket]=count;global_counts[bucket]=global_counts.get(bucket,0)+count
            if marked:marks[source,bucket]=marked
        maximum=max(global_counts.values(),default=1);bar_width=width/data['bins']
        painter.setFont(self.font());painter.setPen(muted)
        painter.drawText(16,63,'Densité globale')
        painter.drawText(16,83,'Échelle logarithmique')
        for bucket,count in global_counts.items():
            height=47*math.log1p(count)/math.log1p(maximum)
            painter.fillRect(QRectF(left+bucket*bar_width,92-height,max(1,bar_width-1),height),QColor(COLORS[0]))
        ticks=max(2,min(5,int(width//180)+1))
        for tick in range(ticks):
            x=left+width*tick/(ticks-1)
            painter.setPen(QPen(palette.color(QPalette.Mid),1,Qt.DotLine))
            painter.drawLine(QPointF(x,100),QPointF(x,self.height()-28))
            value=data['start']+(data['end']-data['start'])*tick//(ticks-1)
            label=utc_label(value).replace(' UTC','')
            span=data['end']-data['start']
            if span>86_400*1_000_000_000:label=label[:16]
            elif span>=1_000_000_000:label=label[11:23]
            else:label=label[11:]
            painter.setPen(muted);painter.drawText(QRectF(max(left,min(left+width-180,x-90)),96,180,18),Qt.AlignCenter,label)
        for lane,source in enumerate(self.sources):
            y=self.TOP+lane*self.LANE
            if lane%2==0:painter.fillRect(QRectF(0,y,self.width(),self.LANE),palette.color(QPalette.AlternateBase))
            color=QColor(COLORS[source['id']%len(COLORS)])
            painter.fillRect(QRectF(12,y+10,4,18),color);painter.setPen(text)
            label=painter.fontMetrics().elidedText(source['name'],Qt.ElideMiddle,self.LEFT-35)
            painter.drawText(24,y+16,label);painter.setPen(muted)
            painter.drawText(24,y+31,f"{source['dated']:,} datés".replace(',',' '))
            peak=max((count for (s,b),count in counts.items() if s==source['id']),default=1)
            for (s,bucket),count in counts.items():
                if s!=source['id']:continue
                opacity=.3+.7*math.log1p(count)/math.log1p(peak);fill=QColor(color);fill.setAlphaF(opacity)
                painter.fillRect(QRectF(left+bucket*bar_width,y+7,max(2,bar_width-1),24),fill)
                if (s,bucket) in marks:
                    x=left+(bucket+.5)*bar_width
                    painter.setPen(QPen(QColor('#7a5900'),1));painter.setBrush(QColor('#f7cf55'))
                    painter.drawPolygon(QPolygonF([QPointF(x,y+3),QPointF(x-4,y+10),QPointF(x+4,y+10)]))
        painter.setPen(muted)
        painter.drawText(QRectF(left,self.height()-26,width,22),Qt.AlignLeft,utc_label(data['start']))
        painter.drawText(QRectF(left,self.height()-26,width,22),Qt.AlignRight,utc_label(data['end']))
        if self.selected_time is not None and data['start']<=self.selected_time<=data['end']:
            x=left+width*(self.selected_time-data['start'])/max(1,data['end']-data['start'])
            painter.setPen(QPen(palette.color(QPalette.Text),1,Qt.DashLine));painter.drawLine(QPointF(x,42),QPointF(x,self.height()-28))
            for lane,source in enumerate(self.sources):
                if source['id']==self.selected_source:
                    painter.setBrush(palette.color(QPalette.Base));painter.setPen(QPen(QColor(COLORS[source['id']%len(COLORS)]),2))
                    painter.drawEllipse(QPointF(x,self.TOP+lane*self.LANE+19),5,5)
        if self.drag is not None and self.cursor is not None:
            x1=max(left,min(self.drag,self.cursor));x2=min(self.width()-24,max(self.drag,self.cursor))
            color=QColor(COLORS[0]);color.setAlpha(65)
            painter.fillRect(QRectF(x1,38,max(1,x2-x1),self.height()-65),color)
            painter.setPen(QPen(QColor(COLORS[0]),1));painter.drawRect(QRectF(x1,38,max(1,x2-x1),self.height()-65))

    def wheelEvent(self,event):
        if self.histogram and event.position().x()>=self.LEFT:
            ratio=(event.position().x()-self.LEFT)/max(1,self.width()-self.LEFT-24)
            self.zoomRequested.emit(.5 if event.angleDelta().y()>0 else 2.,max(0.,min(1.,ratio)));event.accept()
        else:super().wheelEvent(event)

    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton and self.histogram:
            if event.position().x()<self.LEFT:
                lane=int((event.position().y()-self.TOP)//self.LANE)
                if 0<=lane<len(self.sources):self.sourceSelected.emit(self.sources[lane]['id'])
            else:self.drag=event.position().x();self.cursor=self.drag;self.update()

    def mouseMoveEvent(self,event):
        if self.drag is not None:self.cursor=event.position().x();self.update();return
        if not self.histogram:return
        lane=int((event.position().y()-self.TOP)//self.LANE)
        time=self.position_time(event.position().x())
        if event.position().x()>=self.LEFT and 0<=lane<len(self.sources):
            bucket=(time-self.histogram['start'])//self.histogram['width']
            count,marked=next(((n,m) for s,b,n,m in self.histogram['rows'] if s==self.sources[lane]['id'] and b==bucket),(0,0))
            QToolTip.showText(event.globalPosition().toPoint(),f"{self.sources[lane]['name']}\n{utc_label(time)}\n{count} événement(s) · {marked} signet(s) dans cette tranche",self)

    def mouseReleaseEvent(self,event):
        if self.drag is not None:
            first=self.position_time(min(self.drag,event.position().x()));last=self.position_time(max(self.drag,event.position().x()))
            distance=abs(event.position().x()-self.drag);self.drag=None;self.cursor=None;self.update()
            if distance>5:self.rangeSelected.emit(first,last)

    def mouseDoubleClickEvent(self,event):
        if self.histogram and event.position().x()>=self.LEFT:
            self.drag=None;self.zoomRequested.emit(.5,max(0.,min(1.,(event.position().x()-self.LEFT)/max(1,self.width()-self.LEFT-24))))


class TimelineModel(QAbstractTableModel):
    HEADERS=['Date UTC','Analyse','Ligne source','Résumé','Note']
    def __init__(self,parent=None):super().__init__(parent);self.rows=[];self.sources=[]
    def replace(self,rows,sources):
        self.beginResetModel();self.rows=rows;self.sources=sources;self.endResetModel()
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.rows)
    def columnCount(self,parent=QModelIndex()):return len(self.HEADERS)
    def headerData(self,section,orientation,role=Qt.DisplayRole):
        if orientation==Qt.Horizontal and role==Qt.DisplayRole:return self.HEADERS[section]
    def data(self,index,role=Qt.DisplayRole):
        if not index.isValid():return None
        row=self.rows[index.row()]
        if role==Qt.ToolTipRole and index.column()==1:return self.sources[row[0]]['path']
        if role in (Qt.DisplayRole,Qt.ToolTipRole):
            values=[utc_label(row[2])+(' *' if row[7] else ''),self.sources[row[0]]['name'],row[1],row[4],row[5] or '']
            return str(values[index.column()])[:1000 if role==Qt.DisplayRole else 10000]
        if role==Qt.FontRole and row[6]:font=QFont();font.setBold(True);return font


class TimelinePanel(QWidget):
    progress=Signal(str)
    def __init__(self,window):
        super().__init__();self.window=window;self.store=None;self.worker_store=None;self.reader=None
        self.documents=[];self.columns={};self.loading=False;self.bounds=None;self.full_bounds=None;self.pending_job=None
        self.back_stack=[];self.offset=0;self.source_filter=None;self.saved_bounds=None;self.saved_sources=None;self.applied_filters={};self.built_respect=False;self.state_loaded=False
        layout=QVBoxLayout(self)
        heading=QHBoxLayout();title=QLabel('Chronologie');title.setStyleSheet('font-size:20px;font-weight:bold;');heading.addWidget(title);heading.addStretch()
        self.events_visible=QCheckBox('Événements');self.events_visible.setChecked(True);heading.addWidget(self.events_visible)
        self.details_visible=QCheckBox('Détails');self.details_visible.setChecked(True);heading.addWidget(self.details_visible)
        self.focus_button=QPushButton('Agrandir');self.focus_button.clicked.connect(lambda: self.window.workspace_layout.leave_focus() if self.window.workspace_layout.focused else self.window.workspace_layout.timeline());heading.addWidget(self.focus_button)
        layout.addLayout(heading)
        intro=QLabel('Reliez les utilisateurs, IP, chemins et empreintes entre analyses. Glissez sur le graphique pour isoler une période ; la molette zoome autour du pointeur.')
        intro.setWordWrap(True);self.setToolTip(intro.text());intro.deleteLater()
        controls=FlowLayout();self.build_button=QPushButton('Actualiser');self.configure_button=QPushButton('Sources et dates…')
        self.build_button.clicked.connect(self.rebuild);self.configure_button.clicked.connect(self.configure)
        self.respect=QCheckBox('Appliquer les filtres des analyses');controls.addWidget(self.build_button);controls.addWidget(self.configure_button);controls.addWidget(self.respect)
        self.stop=QPushButton('Interrompre');self.stop.clicked.connect(self.interrupt);self.stop.setEnabled(False);controls.addWidget(self.stop);controls.addStretch();layout.addLayout(controls)
        query=FlowLayout();self.kind=QComboBox()
        for value,label in KINDS.items():self.kind.addItem(label,value)
        self.query=QLineEdit();self.query.setPlaceholderText('Utilisateur, IP, chemin, empreinte ou texte…')
        self.query.setClearButtonEnabled(True)
        self.kind.setToolTip('Types reconnus par le nom des colonnes ; utilisez « Tout le texte » pour les autres schémas.')
        self.exact_tip='Comparer la valeur complète du champ, sans tenir compte des majuscules ; aucune identité ni adresse n’est déduite automatiquement.'
        self.exact=QCheckBox('Valeur exacte');self.bookmarks=QCheckBox('Signets');self.undated=QCheckBox('Inclure sans date');self.undated.setChecked(True)
        self.exact.setToolTip(self.exact_tip);self.respect.setToolTip('Option appliquée lors de la prochaine construction / actualisation de l’index.')
        self.apply_button=QPushButton('Corréler');self.apply_button.clicked.connect(self.apply_query);self.query.returnPressed.connect(self.apply_query)
        for widget in (self.kind,self.query,self.exact,self.bookmarks,self.undated,self.apply_button):query.addWidget(widget,1 if widget==self.query else 0)
        layout.addLayout(query)
        nav=FlowLayout()
        for label,callback in [('Vue globale',self.fit),('Retour',self.back),('−',lambda:self.zoom(2)),('+',lambda:self.zoom(.5)),('←',lambda:self.pan(-.5)),('→',lambda:self.pan(.5)),('Toutes les pistes',self.all_sources)]:
            button=QPushButton(label);button.clicked.connect(callback);nav.addWidget(button)
        self.period = QComboBox()
        for label, seconds in [('Durée…', 0), ('15 minutes', 900), ('1 heure', 3600), ('24 heures', 86400), ('7 jours', 604800)]:self.period.addItem(label, seconds)
        self.period.activated.connect(lambda _: self.select_duration(self.period.currentData()))
        nav.addWidget(self.period)
        dates_toggle = QPushButton('Dates…');dates_toggle.setCheckable(True);nav.addWidget(dates_toggle)
        nav.addStretch();layout.addLayout(nav)
        self.date_controls = QWidget();nav=FlowLayout(self.date_controls);nav.setContentsMargins(0,0,0,0)
        dates_toggle.toggled.connect(self.date_controls.setVisible)
        self.start=QLineEdit();self.start.setPlaceholderText('Début ISO UTC');self.end=QLineEdit();self.end.setPlaceholderText('Fin ISO UTC')
        self.start.setMinimumWidth(150);self.end.setMinimumWidth(150);nav.addWidget(self.start,1);nav.addWidget(self.end,1)
        range_button=QPushButton('Période');range_button.clicked.connect(self.apply_dates);nav.addWidget(range_button);layout.addWidget(self.date_controls);self.date_controls.hide()
        self.stats=QLabel('Choisissez les sources, puis actualisez la chronologie.');self.stats.setTextFormat(Qt.PlainText);self.stats.setWordWrap(True);layout.addWidget(self.stats)
        self.progress.connect(self.stats.setText)
        self.overview=TimelineOverview();self.overview.setFixedHeight(58);self.overview.centered.connect(self.center_on);layout.addWidget(self.overview)
        self.splitter=QSplitter(Qt.Vertical)
        scroll=QScrollArea();scroll.setWidgetResizable(True);self.canvas=TimelineCanvas();scroll.setWidget(self.canvas);self.splitter.addWidget(scroll)
        bottom=QSplitter(Qt.Horizontal);self.table=QTableView();self.model=TimelineModel(self);self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.table.setAlternatingRowColors(True);self.table.setWordWrap(False)
        self.table.verticalHeader().hide();self.table.horizontalHeader().setSectionsMovable(True);self.table.horizontalHeader().setStretchLastSection(True)
        for column,width in enumerate((230,170,95,330,160)):self.table.setColumnWidth(column,width)
        bottom.addWidget(self.table);self.details=QTextBrowser();bottom.addWidget(self.details);
        self.events_visible.toggled.connect(bottom.setVisible);self.details_visible.toggled.connect(self.details.setVisible);bottom.setSizes([900,260]);self.splitter.addWidget(bottom)
        self.splitter.setChildrenCollapsible(True);self.splitter.setStretchFactor(0,3);self.splitter.setStretchFactor(1,1);self.splitter.setSizes([460,180]);layout.addWidget(self.splitter,1)
        footer=FlowLayout();self.previous=QPushButton('Précédent');self.next=QPushButton('Suivant');self.open_button=QPushButton('Ouvrir la ligne source')
        self.page_label=QLabel();self.previous.clicked.connect(lambda:self.move_page(-1));self.next.clicked.connect(lambda:self.move_page(1));self.open_button.clicked.connect(self.open_source)
        for widget in (self.previous,self.next,self.page_label,self.open_button):footer.addWidget(widget)
        export_button=QPushButton('Exporter la chronologie…');export_button.clicked.connect(self.export_csv);footer.addWidget(export_button)
        footer.addStretch();layout.addLayout(footer)
        self.notice=QLabel('Triangles : signets · Instantané à actualiser après modification des analyses. * Date sans fuseau : position UTC supposée, à vérifier. Résumés limités à 1000 caractères ; la ligne source conserve les valeurs complètes.')
        self.notice.setWordWrap(True);self.canvas.setToolTip(self.canvas.toolTip()+"\n"+self.notice.text());self.notice.hide()
        self.canvas.rangeSelected.connect(self.select_range);self.canvas.zoomRequested.connect(self.zoom);self.canvas.sourceSelected.connect(self.isolate)
        self.table.doubleClicked.connect(lambda *_:self.open_source());self.table.selectionModel().currentChanged.connect(self.show_details)
        self.open_button.setEnabled(False);self.previous.setEnabled(False);self.next.setEnabled(False)

    def state_path(self):
        data=self.window.active_investigation
        return self.window.investigation_library.folder(data['id'])/'timeline-state.json' if data else None

    def save_state(self):
        path=self.state_path()
        if path:
            try:write_json(path,dict(columns=self.columns,query=self.query.text(),kind=self.kind.currentData(),exact=self.exact.isChecked(),bookmarks=self.bookmarks.isChecked(),respect=self.respect.isChecked(),undated=self.undated.isChecked(),bounds=self.bounds,
                                    sources=[self.documents[i].path for i in self.source_filter] if self.source_filter is not None else None))
            except OSError as exc:self.window.statusBar().showMessage('Réglages de chronologie non enregistrés : '+str(exc))

    def load_state(self):
        self.state_loaded=True
        path=self.state_path()
        if path and path.exists():
            try:
                if path.stat().st_size>1024*1024:raise ValueError('Réglages trop volumineux')
                data=json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(data,dict):raise ValueError('Réglages invalides')
                columns=data.get('columns',{})
                if not isinstance(columns,dict) or len(columns)>1000 or any(not isinstance(k,str) or v is not None and (type(v) is not int or not 0<=v<10000) for k,v in columns.items()):
                    raise ValueError('Colonnes temporelles invalides')
                self.columns=columns;self.query.setText(str(data.get('query',''))[:10000])
                index=self.kind.findData(data.get('kind','text'));self.kind.setCurrentIndex(max(0,index))
                self.exact.setChecked(bool(data.get('exact')));self.bookmarks.setChecked(bool(data.get('bookmarks')));self.respect.setChecked(bool(data.get('respect')))
                self.undated.setChecked(bool(data.get('undated',True)))
                bounds=data.get('bounds')
                if bounds is not None and (not isinstance(bounds,list) or len(bounds)!=2 or any(type(n) is not int or abs(n)>10**30 for n in bounds) or bounds[0]>bounds[1]):
                    raise ValueError('Période de chronologie invalide')
                self.saved_bounds=tuple(bounds) if bounds else None
                sources=data.get('sources')
                if sources is not None and (not isinstance(sources,list) or len(sources)>1000 or any(not isinstance(p,str) for p in sources)):
                    raise ValueError('Sources de chronologie invalides')
                self.saved_sources=sources
            except (OSError,ValueError,TypeError) as exc:
                self.columns={};self.saved_bounds=None;self.saved_sources=None
                self.window.statusBar().showMessage('Réglages de chronologie ignorés : '+str(exc))

    def configure(self):
        if self.loading or not self.window.can_open_file():return
        if not self.state_loaded:self.load_state()
        self.window.remember_active()
        if not self.window.documents:return
        dialog=QDialog(self);dialog.setWindowTitle('Sources et dates de la chronologie');dialog.resize(740,480)
        layout=QVBoxLayout(dialog);hint=QLabel('Choisissez la date qui représente l’événement de chaque analyse. Les autres dates restent disponibles dans la ligne source. Les lignes sans date restent recherchables mais ne sont pas dessinées.')
        hint.setText(hint.text()+' Pour une date locale, créez d’abord une colonne UTC dans Analyses puis choisissez-la ici.')
        hint.setWordWrap(True);layout.addWidget(hint)
        def source_headers():
            reader=WorkspaceReader(self.window.documents,self.window.settings,self.window.case);result={}
            for document in reader.documents:
                try:
                    with reader.open(document) as case:result[document.path]=list(case.headers)
                except Exception:result[document.path]=document.source_info['headers']
            return result
        actual_headers=self.window.connection_work(source_headers,'Lecture des colonnes temporelles…')
        table=QTableWidget(len(self.window.documents),3);table.setHorizontalHeaderLabels(['Analyse','Colonne temporelle','Dernier état de l’index'])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);combos=[]
        for i,document in enumerate(self.window.documents):
            item=QTableWidgetItem(Path(document.source_info['path']).name);item.setFlags(item.flags()&~Qt.ItemIsEditable);item.setToolTip(document.path);table.setItem(i,0,item)
            combo=QComboBox();combo.addItem('Sans date / corrélation uniquement',None)
            headers=actual_headers[document.path]
            for index,header in enumerate(headers):combo.addItem(header,index)
            value=self.columns.get(document.path,guess_time_column(headers,document.view.timestamp_columns))
            combo.setCurrentIndex(max(0,combo.findData(value)));table.setCellWidget(i,1,combo);combos.append(combo)
            source=next((s for s in self.store.sources if s['path']==document.path),None) if self.store else None
            status=source['error'] or f"{source['dated']} datés · {source['undated']} sans date" if source else 'Non indexé'
            item=QTableWidgetItem(status);item.setFlags(item.flags()&~Qt.ItemIsEditable);item.setToolTip(status);table.setItem(i,2,item)
        layout.addWidget(table);buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        try:
            if dialog.exec()==QDialog.Accepted:
                self.columns={doc.path:combo.currentData() for doc,combo in zip(self.window.documents,combos)};self.save_state();self.rebuild()
        finally:dialog.deleteLater()

    def filters(self,dates=True):
        value=dict(sources=self.source_filter,text=self.query.text(),kind=self.kind.currentData(),exact=self.exact.isChecked(),bookmarks=self.bookmarks.isChecked(),include_undated=self.undated.isChecked())
        if dates and self.bounds:value.update(start=self.bounds[0],end=self.bounds[1])
        return value

    def busy(self,value):
        self.loading=value;self.stop.setEnabled(value)
        if not value:self.pending_job=None
        for widget in (self.build_button,self.configure_button,self.apply_button,self.query,self.kind,self.exact,self.bookmarks,self.undated,self.respect,self.start,self.end):widget.setEnabled(not value)

    def rebuild(self):
        if self.loading or not self.window.can_open_file():return
        if not self.window.documents:self.stats.setText('Ouvrez des analyses pour construire la chronologie.');return
        self.window.remember_active();documents=copy.deepcopy(self.window.documents)
        if not self.state_loaded:self.load_state()
        if [d.path for d in self.documents] != [d.path for d in documents]:
            self.source_filter=[i for i,d in enumerate(documents) if d.path in self.saved_sources] if self.saved_sources is not None else None
        columns={doc.path:self.columns.get(doc.path,guess_time_column(doc.source_info['headers'],doc.view.timestamp_columns)) for doc in documents}
        reader=WorkspaceReader(documents,self.window.settings,self.window.case);self.reader=reader
        filters=self.filters(False);respect=self.respect.isChecked();wanted_bounds=self.bounds if self.store else self.saved_bounds
        self.busy(True);self.stats.setText('Construction de l’index sur disque… Les événements sources ne sont pas modifiés.')
        def work():
            candidate=TimelineStore(memory_mb=self.window.settings.memory_mb);self.worker_store=candidate
            try:
                candidate.build(reader,columns,respect,progress=self.progress.emit);reader.check()
                extent=candidate.extent(**filters)
                full_bounds=(int(extent[0]),int(extent[1])) if extent[0] is not None else None
                bounds=wanted_bounds if wanted_bounds and full_bounds else full_bounds
                if bounds:filters.update(start=bounds[0],end=bounds[1])
                page=candidate.page(**filters)
                chart_filters={k:v for k,v in filters.items() if k not in ('include_undated','start','end')}
                histogram=candidate.histogram(*bounds,**chart_filters) if bounds else None
                overview=candidate.histogram(*full_bounds,**chart_filters) if full_bounds and bounds!=full_bounds else histogram
                return candidate,bounds,page,histogram,overview,full_bounds
            except BaseException:candidate.close();raise
            finally:self.worker_store=None
        def done(result):
            old=self.store;self.store,self.bounds,page,histogram,overview,full_bounds=result
            if old:old.close()
            self.reader=None;self.busy(False);self.documents=documents;self.columns=columns;self.full_bounds=full_bounds;self.back_stack=[];self.offset=0
            self.saved_bounds=None;self.saved_sources=None;self.applied_filters=copy.deepcopy(filters);self.built_respect=respect
            self.overview.display(overview,self.bounds)
            self.show_result(page,histogram);self.save_state()
            self.window.coverage_panel.record_timeline(self)
        self.pending_job=self.window.run(work,done,on_error=self.failed,on_cancel=lambda:self.failed('Construction interrompue ; l’index précédent est conservé.'),coverage_stage='Chronologie')

    def failed(self,message):
        self.reader=None;self.busy(False);self.stats.setText(str(message))

    def interrupt(self):
        if self.pending_job:self.pending_job.cancel()
        if self.reader:self.reader.interrupt()
        if self.worker_store:self.worker_store.interrupt()
        elif self.loading and self.store:self.store.interrupt()

    def refresh(self,fit=False):
        if self.loading or not self.store or not self.window.can_open_file():return
        filters=self.filters(not fit);store=self.store;offset=self.offset
        self.busy(True)
        def work():
            extent=store.extent(**{k:v for k,v in filters.items() if k not in ('start','end')})
            bounds=(int(extent[0]),int(extent[1])) if fit and extent[0] is not None else (None if fit else self.bounds)
            if bounds:filters.update(start=bounds[0],end=bounds[1])
            page=store.page(offset=offset,**filters)
            chart_filters={k:v for k,v in filters.items() if k not in ('start','end','include_undated')}
            histogram=store.histogram(*bounds,**chart_filters) if bounds else None
            return bounds,page,histogram
        def done(result):
            self.busy(False);self.bounds,page,histogram=result
            self.applied_filters=copy.deepcopy(filters)
            if fit:self.full_bounds=self.bounds;self.overview.display(histogram,self.bounds)
            else:self.overview.display(self.overview.histogram,self.bounds)
            self.show_result(page,histogram);self.save_state()
        self.pending_job=self.window.run(work,done,on_error=self.failed,on_cancel=lambda:self.failed('Requête interrompue.'),coverage_stage='Chronologie')

    def show_result(self,page,histogram):
        sources=self.store.sources
        visible=[s for s in sources if self.source_filter is None or s['id'] in self.source_filter]
        self.canvas.display(histogram,visible);self.model.replace(page['rows'],sources)
        self.details.clear();self.open_button.setEnabled(bool(page['rows']))
        if page['rows']:self.table.setCurrentIndex(self.model.index(0,0))
        self.previous.setEnabled(self.offset>0);self.next.setEnabled(self.offset+len(page['rows'])<page['count'])
        self.page_label.setText(f"{self.offset+1 if page['rows'] else 0}–{self.offset+len(page['rows'])} / {page['count']:,}".replace(',',' '))
        errors=[s['name']+' : '+s['error'] for s in sources if s['error']]
        self.stats.setText(f"{page['count']:,} correspondance(s) · {len(sources)} analyses · {sum(s['undated'] for s in sources):,} sans date exploitable · {sum(s['naive'] for s in sources):,} dates sans fuseau explicite".replace(',',' ')+
            (f'\n{len(errors)} analyse(s) en erreur : '+' ; '.join(message[:350] for message in errors[:3])+('… Détails dans Sources et dates.' if len(errors)>3 else '') if errors else ''))
        if self.bounds:
            self.start.setText(utc_label(self.bounds[0]).replace(' UTC','Z').replace(' ','T'))
            self.end.setText(utc_label(self.bounds[1]).replace(' UTC','Z').replace(' ','T'))
        else:self.start.clear();self.end.clear()

    def apply_query(self):
        if self.loading:return
        self.offset=0
        if self.store and [(d.path,d.source_info) for d in self.documents] == [(d.path,d.source_info) for d in self.window.documents]:self.refresh(fit=True)
        else:self.rebuild()

    def select_duration(self, seconds):
        if not seconds or not self.bounds or self.loading:return
        center = self.canvas.selected_time if self.canvas.selected_time is not None else sum(self.bounds)//2
        half = seconds*1_000_000_000//2
        self.select_range(center-half, center+half)

    def fit(self):
        if not self.loading:self.offset=0;self.back_stack=[];self.refresh(fit=True)
    def select_range(self,start,end):
        if self.loading or not self.store:return
        if end<start:start,end=end,start
        if self.bounds:self.back_stack.append(self.bounds);self.back_stack=self.back_stack[-30:]
        self.bounds=(int(start),max(int(start),int(end)));self.offset=0;self.refresh()
    def zoom(self,factor,anchor=.5):
        if self.loading or not self.bounds:return
        start,end=self.bounds;span=max(1,end-start);center=start+int(span*anchor)
        new_span=max(1,int(span*factor))
        self.select_range(center-int(new_span*anchor),center+int(new_span*(1-anchor)))
    def pan(self,factor):
        if self.bounds and not self.loading:
            shift=int(max(1,self.bounds[1]-self.bounds[0])*factor) or (1 if factor>0 else -1);self.select_range(self.bounds[0]+shift,self.bounds[1]+shift)
    def center_on(self,time):
        if self.bounds and not self.loading:
            span=max(1,self.bounds[1]-self.bounds[0]);self.select_range(time-span//2,time+span//2)
    def back(self):
        if not self.loading and self.back_stack:self.bounds=self.back_stack.pop();self.offset=0;self.refresh()
    def all_sources(self):
        if not self.loading:self.source_filter=None;self.offset=0;self.refresh(fit=True)
    def isolate(self,source):
        if not self.loading:self.source_filter=[source];self.offset=0;self.refresh(fit=True)
    def move_page(self,direction):
        if not self.loading:self.offset=max(0,self.offset+direction*self.store.PAGE_SIZE);self.refresh()
    def apply_dates(self):
        if self.loading or not self.store:return
        try:
            start=self.store.parse_time(self.start.text());end=self.store.parse_time(self.end.text())
            if end<start:raise ValueError('La fin doit suivre le début')
            self.select_range(start,end)
        except ValueError as exc:self.stats.setText(str(exc))

    def show_details(self,index,*_):
        if not index.isValid() or index.row()>=len(self.model.rows):self.open_button.setEnabled(False);return
        row=self.model.rows[index.row()];source=self.store.sources[row[0]]
        self.canvas.selected_time=row[2];self.canvas.selected_source=row[0];self.canvas.update()
        self.open_button.setEnabled(True)
        self.details.setPlainText(f"{utc_label(row[2])}\n\nDate source ({source.get('column_name') or 'aucune colonne'}) : {row[3] or 'Absente'}\n"+
            ('Attention : fuseau absent ; position UTC supposée.\n' if row[7] else '')+
            f"\nAnalyse : {source['path']}\nLigne source : {row[1]}\n\n{row[4] or ''}\n\nNote : {row[5] or 'Aucune'}")

    def open_source(self):
        if self.loading or not self.window.can_open_file():return
        index=self.table.currentIndex()
        if not index.isValid():return
        row=self.model.rows[index.row()];document=self.documents[row[0]]
        target=next((i for i,d in enumerate(self.window.documents) if d.path==document.path and d.source_info==document.source_info),None)
        if target is None:self.stats.setText('L’analyse a changé ; reconstruisez la chronologie.');return
        if getattr(self.window,'ioc_panel',None):self.window.ioc_panel.restore_origin(refresh=False)
        previous=self.window._timeline_origin
        if previous and previous.path!=document.path:self.window.restore_timeline_origin(refresh=False)
        self.window.switch_document(target)
        if self.window.case and str(self.window.case.path)==document.path:
            if not self.window._timeline_origin:self.window._timeline_origin=copy.deepcopy(self.window.snapshot_analysis())
            self.window.timeline_return_action.setVisible(True);self.window.timeline_return_action.setEnabled(True)
            self.window.set_view(View(filters=[Filter(-1,'eq',str(row[1]))]))
            self.window.workbench.setCurrentIndex(0)

    def correlate(self,value,kind='text'):
        if self.loading:return
        if not self.state_loaded:self.load_state()
        self.saved_bounds=None;self.saved_sources=None
        self.query.setText(value);self.kind.setCurrentIndex(max(0,self.kind.findData(kind)));self.exact.setChecked(kind!='text');self.source_filter=None
        self.apply_query()

    def reset_workspace(self):
        if self.store:self.store.close();self.store=None
        self.columns={};self.documents=[];self.bounds=None;self.source_filter=None;self.offset=0;self.back_stack=[]
        self.saved_bounds=None;self.saved_sources=None;self.applied_filters={};self.state_loaded=False
        self.canvas.display(None,[]);self.overview.display(None,None);self.model.replace([],[]);self.details.clear();self.query.clear();self.stats.setText('Espace de travail changé : reconstruisez la chronologie.');self.open_button.setEnabled(False)
        self.page_label.clear();self.previous.setEnabled(False);self.next.setEnabled(False);self.start.clear();self.end.clear()
        self.canvas.selected_time=None;self.canvas.selected_source=None
        self.window._timeline_origin=None;self.window.timeline_return_action.setVisible(False)

    def export_csv(self,path=None):
        if self.loading or not self.store or not self.window.can_open_file():return
        if not path:path,_=QFileDialog.getSaveFileName(self,'Exporter la chronologie filtrée','chronologie.csv','CSV (*.csv)')
        if not path or not self.window.investigation_destination_is_safe(path):return
        filters=copy.deepcopy(self.applied_filters);store=self.store;self.busy(True)
        def done(receipt):
            self.busy(False);self.stats.setText(f"Chronologie exportée : {receipt['written']} événements · {path}");self.window.coverage_panel.export_done(receipt)
        self.pending_job=self.window.run(lambda:store.export_csv(path,receipt=True,**filters),done,exclusive=True,on_error=self.failed,on_cancel=lambda:self.failed('Export annulé.'),coverage_stage='Export',coverage_context=path)


class TimelineMixin:
    def setup_timeline(self):
        self._timeline_origin=None
        self.timeline_panel=TimelinePanel(self)
        self.timeline_host=QScrollArea();self.timeline_host.setWidgetResizable(True)
        self.timeline_host.setFrameShape(QScrollArea.NoFrame);self.timeline_host.setWidget(self.timeline_panel)
        # Reserve native scrollbar width too: Windows may need a vertical bar
        # after wrapping tools, which must not clip the graph horizontally.
        minimum = max(540,self.timeline_panel.minimumSizeHint().width())
        self.timeline_host.setMinimumWidth(minimum+self.timeline_host.style().pixelMetric(QStyle.PM_ScrollBarExtent))
        self.timeline_tab_index=self.workbench.addTab(self.timeline_host,'Chronologie & corrélations')
        self.workbench.currentChanged.connect(lambda index:self.timeline_panel.load_state() if index==self.timeline_tab_index and not self.timeline_panel.state_loaded else None)
        menu=next(a.menu() for a in self.menuBar().actions() if a.text().replace('&','')=='Analyse')
        action=QAction('Chronologie & corrélations',self);action.triggered.connect(self.show_timeline);menu.addAction(action)
        self.timeline_return_action=QAction('Revenir à la chronologie',self)
        self.timeline_return_action.setToolTip('Retrouver la chronologie et restaurer la vue de l’analyse avant le saut à la ligne source.')
        self.timeline_return_action.triggered.connect(self.return_to_timeline)
        self.timeline_return_action.setVisible(False);self.main_toolbar.addAction(self.timeline_return_action)

    def show_timeline(self):
        self.workbench.setCurrentIndex(self.timeline_tab_index)
        if not getattr(self, '_closing_workspace', False) and self.documents and not self.timeline_panel.store and not self.timeline_panel.loading:
            self.timeline_panel.rebuild()

    def restore_timeline_origin(self,refresh=True):
        origin=self._timeline_origin
        if origin:
            index=next((i for i,d in enumerate(self.documents) if d.path==origin.path and d.source_info==origin.source_info),None)
            if index is not None:
                if self.case and str(self.case.path)==origin.path:
                    if refresh:self.set_view(copy.deepcopy(origin.view))
                    else:self.view=copy.deepcopy(origin.view)
                    if origin.header_state:self.tree.header().restoreState(origin.header_state)
                self.documents[index]=origin
        self._timeline_origin=None;self.timeline_return_action.setVisible(False)

    def return_to_timeline(self):
        if not self.can_open_file():return
        self.restore_timeline_origin();self.show_timeline()

    def correlate_value(self,column,value):
        if value is None or not self.can_open_file():return
        kind=field_kind(self.case.headers[column]) or 'text'
        self.show_timeline();self.timeline_panel.correlate(str(value),kind)
