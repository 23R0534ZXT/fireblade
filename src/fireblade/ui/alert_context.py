"""Alert-to-EVTX navigation in ordinary Fireblade analysis tabs."""
import json
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget

from fireblade.core.collection import Collection
from fireblade.core.alert_context import build_context, sources, retain_context, discard_preview
from fireblade.core.engine import Case
from fireblade.core.models import Filter, View


class AlertContextMixin:
    def setup_alert_context(self):
        self._context_bar=None
        self._context_navigation=None
        self._context_source_analysis=None
        self._context_source_role=None
        self._preview_result=None
        self._preview_collection=None
        self.context_preview=None
        self.context_action=QAction('Voir le contexte EVTX de l’alerte',self)
        self.context_action.triggered.connect(self.preview_alert_context)
        self.context_action.setEnabled(False)
        menu=next(a.menu() for a in self.menuBar().actions() if a.text().replace('&','')=='Analyse')
        menu.addAction(self.context_action)
        self.workbench.currentChanged.connect(lambda index: self.context_preview.hide() if index!=0 and self.context_preview else None)

    def is_hayabusa_analysis(self):
        return self.case is not None and 'Relation à l’alerte' not in self.case.headers and {'RuleTitle','RecordID','Fireblade_EVTX_Source'}.issubset(self.case.headers)

    def alert_document(self):
        if not self.is_hayabusa_analysis() or self.collection is None:return None
        return next((d for d in self.collection.report['documents']
                     if d['path']==str(self.case.path) and d['source']==self.case.info),None)

    def selected_evidence_row(self):
        if not self.case or not self.model or self.model.case is not self.case:return None
        index=self.tree.currentIndex()
        if not index.isValid():return None
        node=self.model.node(index)
        if node.group or len(node.values)!=len(self.case.headers)+1:return None
        return int(node.values[0]),dict(zip(self.case.headers,node.values[1:]))

    def context_metadata(self):
        if not self.case or not self.collection:return None
        document=next((d for d in self.collection.report['documents'] if d['path']==str(self.case.path)),None)
        if document is None or document['source']!=self.case.info:return None
        return next((item for item in self.collection.report.get('contexts',[]) if item['analysis']==str(self.case.path)),None)

    def prepare_context_view(self,case,initial_view,auto_layout):
        relevant='Relation à l’alerte' in case.headers or {'RuleTitle','RecordID','Fireblade_EVTX_Source'}.issubset(case.headers)
        if not relevant:return initial_view,auto_layout
        document=next((d for d in self.collection.report['documents'] if d['path']==str(case.path)),None) if self.collection else None
        if document is None:
            folder=case.path.parent.parent
            if (folder/'collection.json').is_file():
                try:
                    candidate=self.connection_work(lambda:Collection.reopen(folder,self.toolpack(),self.settings))
                    document=next((d for d in candidate.report['documents'] if d['path']==str(case.path)),None)
                    if document is not None:self.collection=candidate
                except Exception as exc:self.statusBar().showMessage('Collecte associée indisponible : '+str(exc))
        if document is not None:
            if initial_view is None:initial_view=View.from_json(json.dumps(document['view']))
            if auto_layout is None:auto_layout=False
        return initial_view,auto_layout

    def ensure_context_bar(self):
        if self._context_bar is not None:return
        self._context_bar=QWidget()
        layout=QVBoxLayout(self._context_bar);layout.setContentsMargins(0,3,0,3)
        self.context_summary=QLabel()
        self.context_summary.setTextFormat(Qt.PlainText)
        self.context_summary.setWordWrap(True)
        layout.addWidget(self.context_summary)
        row=QHBoxLayout()
        self.context_window_label=QLabel('Contexte avant et après :')
        row.addWidget(self.context_window_label)
        self.context_minutes=QSpinBox();self.context_minutes.setRange(1,1440);self.context_minutes.setValue(5)
        self.context_minutes.setSuffix(' min')
        row.addWidget(self.context_minutes)
        row.addStretch()
        layout.addLayout(row)
        actions=QHBoxLayout()
        self.context_open=QPushButton('Voir le contexte de cette alerte')
        self.context_open.clicked.connect(self.preview_alert_context)
        actions.addWidget(self.context_open)
        self.context_source=QPushButton('Ouvrir l’événement EVTX source')
        self.context_source.clicked.connect(self.open_context_source)
        actions.addWidget(self.context_source)
        self.context_return=QPushButton('Revenir aux alertes')
        self.context_return.clicked.connect(self.return_to_alerts)
        actions.addWidget(self.context_return)
        actions.addStretch()
        layout.addLayout(actions)
        self.content_stack.widget(1).layout().insertWidget(0,self._context_bar)

    def update_alert_context_bar(self,*_):
        if not hasattr(self,'context_action'):return
        alert=self.is_hayabusa_analysis()
        metadata=self.context_metadata()
        source=self.case is not None and self._context_source_analysis==str(self.case.path)
        relevant=alert or metadata is not None or source
        row=self.selected_evidence_row() if alert else None
        associated=self.alert_document() is not None
        if self.context_preview and (not alert or not associated or row is None or not self._preview_result or
                self._preview_collection is not self.collection or self._preview_result['alert_analysis']!=str(self.case.path) or self._preview_result['alert_row']!=row[0]):
            self.context_preview.hide()
        self.context_action.setEnabled(alert and row is not None and associated)
        if not relevant:
            if self._context_bar is not None:self._context_bar.hide()
            return
        self.ensure_context_bar();self._context_bar.show()
        self.context_open.setVisible(alert)
        self.context_open.setEnabled(row is not None and associated)
        self.context_source.setVisible(metadata is not None)
        self.context_return.setVisible(not alert)
        self.context_minutes.setVisible(alert)
        self.context_window_label.setVisible(alert)
        if alert:
            text='Sélectionnez une alerte pour ouvrir les événements EVTX autour de sa date, sur la même machine.'
            if row:text='Alerte : '+str(row[1].get('RuleTitle',''))+' · Gravité : '+str(row[1].get('Level',''))
            if not associated:text+=' Reprenez le dossier de collecte pour retrouver ses analyses EVTX.'
        elif metadata:
            text=f"{metadata['rule']} · {metadata['references']} référence(s), {metadata['events']} événement(s) · ± {metadata['minutes']} min."
            if metadata.get('truncated'):text+=' Contexte limité : certains événements ne sont pas affichés.'
            text+=' Les voisins temporels ne sont pas automatiquement suspects.'
            if metadata['notes']:text+=' '+ ' '.join(metadata['notes'][:3])
            self._context_navigation=metadata
        else:
            text='Ouvert depuis le contexte : '+str(self._context_source_role or 'événement EVTX')+'. Effacer les filtres permet de retrouver tous les événements de ce fichier.'
        self.context_summary.setText(text)
        self.context_summary.setToolTip('\n'.join(metadata.get('notes',[])) if metadata else '')

    def configure_context_columns(self):
        if self.context_metadata() is None:return
        widths={'Relation à l’alerte':220,'TimeCreated':235,'Timestamp':235,'EventId':80,'EventID':80,
                'Computer':165,'Channel':105,'MapDescription':360}
        self.tree.frozen_for(0).setColumnWidth(0,70)
        for name,width in widths.items():
            if name in self.case.headers:
                section=self.case.headers.index(name)+1
                self.tree.frozen_for(section).setColumnWidth(section,width)

    def open_alert_context(self):
        if not self.can_open_file():return
        selected=self.selected_evidence_row()
        if self.alert_document() is None or selected is None:
            self.statusBar().showMessage('Sélectionnez une alerte dans une collecte Fireblade.')
            return
        self.remember_collection_views()
        row,alert=selected
        alert_path=str(self.case.path)
        minutes=self.context_minutes.value() if self._context_bar is not None else 5
        collection=self.collection
        def done(result):
            def open_when_idle():
                if self.pool.activeThreadCount():
                    QTimer.singleShot(20,open_when_idle);return
                if self.collection is not collection:return
                self._context_navigation=result
                self.load_case(result['analysis'])
                self.workbench.setCurrentIndex(0)
                self.show_collection_report(collection.report)
            QTimer.singleShot(0,open_when_idle)
        job=self.run(lambda:build_context(collection,alert,alert_path,row,minutes),done,exclusive=True)
        if job is not None:collection.progress=job.signals.progress.emit

    def preview_alert_context(self):
        if not self.can_open_file():return
        selected=self.selected_evidence_row()
        if self.alert_document() is None or selected is None:
            self.statusBar().showMessage('Sélectionnez une alerte dans sa collecte.');return
        row,alert=selected;collection=self.collection;alert_path=str(self.case.path)
        minutes=self.context_minutes.value()
        if self._preview_result and self._preview_collection is collection and all((
                self._preview_result['alert_analysis']==alert_path,self._preview_result['alert_row']==row,
                self._preview_result['minutes']==minutes)):
            self.context_preview.show();return
        self.remember_collection_views()
        old_result=self._preview_result;old_collection=self._preview_collection
        def build():
            result=build_context(collection,alert,alert_path,row,minutes,register=False)
            case=None
            try:
                case=Case(result['analysis'],settings=self.settings,read_only=True)
                document=result['_document']
                view=View.from_json(json.dumps(document['view']))
                rows=[]
                while len(rows)<result['events']:
                    page=case.page(view,offset=len(rows))
                    if not page:break
                    rows.extend(page)
                headers=list(case.headers)
            except BaseException:
                if case:case.close();case=None
                discard_preview(collection,result)
                raise
            finally:
                if case:case.close()
            if old_collection:discard_preview(old_collection,old_result)
            return result,headers,rows
        def display(value):
            result,headers,rows=value
            self._preview_result=result;self._preview_collection=collection
            if self.context_preview is None:
                from fireblade.ui.context_preview import ContextPreview
                self.context_preview=ContextPreview(self)
                self.context_preview.hide()
                self.context_preview.visibilityChanged.connect(self.update_navigation_visibility)
                if self.width()<1100:self.navigator.hide()
                self.addDockWidget(Qt.RightDockWidgetArea,self.context_preview)
                self.context_preview.keep.clicked.connect(self.keep_preview_context)
                self.context_preview.open_source.clicked.connect(self.open_preview_source)
            self.context_preview.display(result,headers,rows)
            if self.width()<1100:self.navigator.hide()
            self.context_preview.show()
            self.resizeDocks([self.context_preview],[max(320,self.width()//2)],Qt.Horizontal)
        job=self.run(build,display,exclusive=True)
        if job is not None:collection.progress=job.signals.progress.emit

    def keep_preview_context(self):
        if not self.can_open_file() or not self._preview_result or self._preview_collection is not self.collection:return
        result=self._preview_result;collection=self.collection
        try:
            self._context_navigation=self.connection_work(lambda:retain_context(collection,result),'Enregistrement du contexte…')
            self.load_case(result['analysis'])
            self.workbench.setCurrentIndex(0);self.show_collection_report(collection.report)
        except Exception as exc:self.error(exc)

    def open_preview_source(self):
        if not self.can_open_file() or self._preview_collection is not self.collection:return
        row=self.context_preview.selected()
        if row is not None:self.open_source_reference(row,self._preview_result)

    def clear_context_preview(self):
        if self.context_preview:self.context_preview.hide()
        if self._preview_collection:
            try:discard_preview(self._preview_collection,self._preview_result)
            except OSError as exc:self.statusBar().showMessage('Contexte temporaire conservé : '+str(exc))
        self._preview_result=None;self._preview_collection=None

    def open_context_source(self):
        if not self.can_open_file() or self.context_metadata() is None:return
        selected=self.selected_evidence_row()
        if selected is None:
            self.statusBar().showMessage('Sélectionnez un événement du contexte.');return
        row=selected[1]
        self.open_source_reference(row,self.context_metadata())

    def open_source_reference(self,row,context):
        path=row.get('Fireblade_Analysis')
        path=self.collection.report.get('portable_relocation',{}).get(path,path)
        known={document['path']:document for document,_ in sources(self.collection.report)}
        if path not in known:
            self.error('Cette référence n’appartient pas aux analyses EVTX de la collecte.');return
        try:
            number=int(row.get('Fireblade_Row',''))
            if number<1:raise ValueError()
            def verify():
                case=Case(path,settings=self.settings,read_only=True)
                try:
                    if case.info!=known[path]['source']:raise ValueError('Analyse EVTX remplacée depuis la collecte')
                finally:case.close()
            self.connection_work(verify)
        except Exception as exc:self.error(str(exc) or 'Référence de ligne invalide');return
        self._context_navigation=context
        self._context_source_analysis=path
        self._context_source_role=row.get('Relation à l’alerte')
        self.load_case(path)
        if self.case and str(self.case.path)==path:
            self.set_view(View(expression=Filter(0,'expression',f'[Line] = {number}')))
            self.update_alert_context_bar()
            self.select_evidence_row(path,number)

    def return_to_alerts(self):
        if not self.can_open_file():return
        context=self.context_metadata() or self._context_navigation
        if context is None:return
        document=next((d for d in self.collection.report['documents'] if d['path']==context['alert_analysis']),None)
        if document is None:
            self.error('Analyse de l’alerte absente de cette collecte.');return
        try:
            def verify():
                case=Case(document['path'],settings=self.settings,read_only=True)
                try:
                    if case.info!=document['source']:raise ValueError('Analyse des alertes remplacée depuis la collecte')
                finally:case.close()
            self.connection_work(verify)
        except Exception as exc:self.error(exc);return
        self.load_case(context['alert_analysis'])
        self.select_evidence_row(context['alert_analysis'],context['alert_row'])

    def select_evidence_row(self,path,number,attempt=0):
        if not self.case or str(self.case.path)!=path or not self.model:return
        for i in range(self.model.rowCount()):
            index=self.model.index(i,0)
            node=self.model.node(index)
            if not node.group and node.values[0]==number:
                self.tree.setCurrentIndex(index);return
        if attempt<50:QTimer.singleShot(50,lambda:self.select_evidence_row(path,number,attempt+1))
