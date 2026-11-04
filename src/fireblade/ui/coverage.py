"""Workspace coverage dashboard and persistent operational incident journal."""
import copy
import json
from pathlib import Path

from PySide6.QtCore import Qt,Signal
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QComboBox,
    QCheckBox,QLineEdit,QTableView,QTextBrowser,QSplitter,QFileDialog,QDialog,QDialogButtonBox,QListWidget,QListWidgetItem)
from fireblade.core.coverage import (FORMAT,MAX_EVENTS,EXPECTED,audit,event,load_state,save_state,load_report,save_report,export_report)
from fireblade.core.workspace_reader import WorkspaceReader
from fireblade.ui.ioc_hunt import Rows


class CoveragePanel(QWidget):
    progress=Signal(str)
    def __init__(self,window):
        super().__init__();self.window=window;self.events=[];self.dropped=0;self.context=None;self.report=None;self.reader=None;self.entries=[];self.stale=True;self.persistence_error='';self.expected_tools=None
        layout=QVBoxLayout(self)
        self.status=QLabel('Couverture non contrôlée. Les données jamais acquises ne peuvent pas être déduites des fichiers présents.');self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText);layout.addWidget(self.status);self.progress.connect(self.status.setText)
        bar=QHBoxLayout();layout.addLayout(bar)
        self.profile=QComboBox()
        for title,value in [('Périmètre observé uniquement','observed'),('Familles Windows attendues','windows'),('Famille CatScale Linux attendue','linux'),('Journaux Linux /var/log/ attendus','linux_logs')]:self.profile.addItem(title,value)
        bar.addWidget(self.profile)
        plan=QPushButton("Ajuster les familles attendues…");plan.clicked.connect(self.configure_plan);bar.addWidget(plan)
        self.profile.currentIndexChanged.connect(lambda _:setattr(self,"expected_tools",None))
        self.deep=QCheckBox('Inventaire, colonnes vides et IDs');self.deep.setChecked(True);layout.addWidget(self.deep)
        self.hashes=QCheckBox('Revérifier les SHA-256 (lecture complète)');bar.addWidget(self.hashes)
        bar=QHBoxLayout();layout.addLayout(bar)
        self.build_button=QPushButton('Contrôler toute la couverture');bar.addWidget(self.build_button);self.build_button.clicked.connect(self.launch)
        stop=QPushButton('Interrompre');bar.addWidget(stop);stop.clicked.connect(window.interrupt_queries)
        bar=QHBoxLayout();layout.addLayout(bar)
        self.mode=QComboBox();self.mode.addItems(['Constats du dernier contrôle','Historique des opérations']);bar.addWidget(self.mode)
        self.level=QComboBox()
        for title,value in [('Toutes les gravités',''),('Erreurs','error'),('À vérifier','warning'),('Informations / périmètre','info')]:self.level.addItem(title,value)
        bar.addWidget(self.level)
        self.search=QLineEdit();self.search.setPlaceholderText('Étape, fichier, cause…');bar.addWidget(self.search)
        self.export_button=QPushButton('Exporter le bilan JSON / CSV');bar.addWidget(self.export_button);self.export_button.clicked.connect(self.export)
        splitter=QSplitter(Qt.Vertical);layout.addWidget(splitter)
        self.table=QTableView();self.model=Rows(['Étape','Gravité','Fichier / périmètre','Cause','Conséquence','Correction proposée'],self);self.table.setModel(self.model);self.table.setSelectionBehavior(QTableView.SelectRows);self.table.setEditTriggers(QTableView.NoEditTriggers);splitter.addWidget(self.table)
        self.details=QTextBrowser();self.details.setOpenLinks(False);splitter.addWidget(self.details)
        self.table.setColumnWidth(0,110);self.table.setColumnWidth(1,100);self.table.setColumnWidth(2,250);self.table.setColumnWidth(3,430);self.table.setColumnWidth(4,320);self.table.setColumnWidth(5,430)
        self.table.clicked.connect(self.show_details)
        for widget in (self.mode,self.level):widget.currentIndexChanged.connect(self.filter)
        self.search.textChanged.connect(self.filter)
        self.badge=QPushButton('');window.statusBar().addPermanentWidget(self.badge);self.badge.clicked.connect(self.open);self.badge.setMaximumWidth(220);self.badge.hide()
    def open(self):
        self.ensure_context();self.filter()
        self.window.coverage_dialog.show();self.window.coverage_dialog.raise_();self.window.coverage_dialog.activateWindow()
    def state_path(self):
        data=self.window.active_investigation
        return self.window.investigation_library.folder(data['id'])/'coverage-state.json' if data else None
    def ensure_context(self):
        path=self.state_path();context=str(path) if path else 'temporary'
        if context==self.context:return
        self.context=context;self.events=[];self.dropped=0;self.report=None;self.stale=True;self.persistence_error='';self.journal_blocked=False;self.report_blocked=False;self.expected_tools=None
        self.profile.setCurrentIndex(0)
        if path and path.exists():
            try:
                value=load_state(path);self.events=value['events'];self.dropped=value.get('dropped',0)
                plan=value.get('plan',{});index=self.profile.findData(plan.get('profile','observed'));self.profile.setCurrentIndex(max(0,index));self.expected_tools=plan.get('readers')
            except Exception as exc:self.journal_blocked=True;self.persistence_error='Journal de couverture non chargé et conservé sans modification : '+str(exc)
        if path and path.with_name('coverage-last.json').exists():
            try:
                self.report=load_report(path.with_name('coverage-last.json'));self.status.setText('Bilan sauvegardé du '+self.report['created']+' ; périmètre à actualiser avant toute conclusion. Les incidents restent dans l’historique.')
            except Exception as exc:self.report_blocked=True;self.persistence_error+=' Bilan précédent non chargé et conservé : '+str(exc)
        self.update_badge()
    def reset_workspace(self):
        self.context=None;self.events=[];self.report=None;self.entries=[];self.model.display([]);self.details.clear();self.stale=True;self.persistence_error='';self.dropped=0;self.expected_tools=None;self.update_badge()
    def record(self,stage,severity,reason,path='',**metrics):
        self.ensure_context()
        encoded=json.dumps(metrics,ensure_ascii=False)
        if len(encoded.encode('utf-8'))>65536:
            retained={k:v for k,v in metrics.items() if k in ('sha256','content_sha256','expected','written','verified_rows','source_rows','analysis','source','partial','truncated','grouped') and isinstance(v,(str,int,bool,float,type(None)))}
            metrics=dict(**retained,details_abridged=True,original_bytes=len(encoded.encode('utf-8')),excerpt=encoded[:12000])
        self.events.append(event(stage,severity,reason,path,**metrics));self.stale=True
        if len(self.events)>MAX_EVENTS:self.dropped+=len(self.events)-MAX_EVENTS;self.events=self.events[-MAX_EVENTS:]
        path=self.state_path()
        def storage_size(item):
            text=json.dumps(item,ensure_ascii=False,indent=2)
            return len(text.encode('utf-8'))+8*(text.count('\n')+1)+2
        budget=sum(storage_size(e) for e in self.events)
        while self.events and budget>7*1024**2:
            budget-=storage_size(self.events.pop(0));self.dropped+=1
        if path and not self.journal_blocked:
            try:save_state(path,dict(format=FORMAT,version=1,events=self.events,dropped=self.dropped,plan=dict(profile=self.profile.currentData(),readers=self.expected_tools)))
            except Exception as exc:self.persistence_error='Journal non sauvegardé : '+str(exc)
        self.update_badge()
        if self.mode.currentIndex()==1:self.filter()
    def update_badge(self):
        incidents=sum(e['severity'] in ('error','warning') for e in self.events)
        findings=self.report['counts'] if self.report else {}
        alerts=findings.get('error',0)+findings.get('warning',0)
        recent_incident=self.stale and self.events and self.events[-1]['severity'] in ('error','warning')
        self.badge.setText('Imports : incident à vérifier' if recent_incident else f'Imports : {alerts} point(s) à vérifier')
        self.badge.setVisible(bool(recent_incident or alerts or self.persistence_error))
        self.badge.setToolTip((self.events[-1]['reason']+'\n' if recent_incident else '')+(self.persistence_error+'\n' if self.persistence_error else '')+f'{alerts} constats actuels ; {incidents} incidents historiques. Ouvrir les causes, impacts et actions de correction.')
    def configure_plan(self):
        self.ensure_context();dialog=QDialog(self);dialog.setWindowTitle('Familles attendues pour cette enquête');layout=QVBoxLayout(dialog)
        hint=QLabel('Cochez uniquement les familles prévues dans votre plan de collecte. Leur absence est un point à vérifier, pas une preuve d’absence sur la machine.');hint.setWordWrap(True);layout.addWidget(hint)
        listing=QListWidget();layout.addWidget(listing)
        selected=set(EXPECTED[self.profile.currentData()] if self.expected_tools is None else self.expected_tools)
        for name in dict.fromkeys([*EXPECTED['windows'],*EXPECTED['linux'],*EXPECTED['linux_logs']]):
            item=QListWidgetItem(name);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Checked if name in selected else Qt.Unchecked);listing.addItem(item)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        try:
            if dialog.exec()==QDialog.Accepted:
                self.expected_tools=[listing.item(i).text() for i in range(listing.count()) if listing.item(i).checkState()==Qt.Checked]
                self.record('Collecte','info','Plan de familles attendues ajusté.',expected_readers=self.expected_tools)
        finally:dialog.deleteLater()
    def record_collection(self,report):
        files=report.get('files',[]);issues=[e for e in files if e.get('status') not in ('complete','companion')]
        self.record('Collecte','warning' if issues or report.get('status')!='complete' else 'info',
                    f"Collecte {report.get('status')} · {len(files)} fichiers inventoriés · {len(issues)} sans réussite complète attestée.",report.get('output',''),
                    issues=[dict(path=e.get('path'),status=e.get('status'),reason=e.get('error') or e.get('reason') or ' ; '.join(str(r.get('error') or ' ; '.join(r.get('warnings',[]))) for r in e.get('runs',[]) if r.get('error') or r.get('warnings')) or 'Consulter les journaux des lecteurs') for e in issues[:100]],omitted_issue_details=max(0,len(issues)-100))
    def record_timeline(self,panel):
        sources=panel.store.sources;errors=[s for s in sources if s.get('error')];undated=sum(s['undated'] for s in sources);naive=sum(s['naive'] for s in sources)
        self.record('Chronologie','warning' if errors or undated or naive else 'info',
                    f"Index construit : {sum(s['dated'] for s in sources)} lignes datées, {undated} sans date ({sum(s.get('empty_dates',0) for s in sources)} absentes, {sum(s.get('invalid_dates',0) for s in sources)} invalides), {naive} sans fuseau et {len(errors)} analyses en erreur.",
                    sources=copy.deepcopy(sources),respect_filters=panel.built_respect)
    def export_done(self,receipt):
        limited=receipt.get('partial') or receipt.get('truncated')
        reason=f"Export vérifié : {receipt['written']} / {receipt['expected']} lignes écrites ; SHA-256 calculé."
        if 'source_rows' in receipt:reason+=f" Base : {receipt['source_rows']} lignes ; {len(receipt.get('columns',[]))} champs exportés ; {receipt.get('available_columns')} colonnes sources disponibles."
        if receipt.get('grouped'):reason+=' Le fichier contient des comptages par groupe.'
        if limited:reason+=' Périmètre partiel ou détails limités : consulter les limites du reçu.'
        self.record('Export','warning' if not receipt['written'] or limited else 'info',reason,receipt['path'],**{k:v for k,v in receipt.items() if k!='path'})
        self.window.statusBar().showMessage(f"Export vérifié : {receipt['written']} lignes · {receipt['path']}")
    def interrupt(self):
        if self.reader:self.reader.interrupt()
    def launch(self):
        if not self.window.can_open_file():return
        self.ensure_context();self.record('Analyse','info','Contrôle de couverture demandé.',verify_hashes=self.hashes.isChecked(),deep_checks=self.deep.isChecked())
        self.window.remember_active();reader=WorkspaceReader(self.window.documents,self.window.settings,self.window.case);self.reader=reader
        active=copy.deepcopy(self.window.collection.report) if self.window.collection else None
        data=self.window.active_investigation;paths=[str(Path(c['path'])/'collection.json') for c in data.get('collections',[])] if data else []
        panel=self.window.timeline_panel;timeline=None
        if panel.store:
            timeline=dict(sources=copy.deepcopy(panel.store.sources),respect_filters=panel.built_respect,include_undated=panel.applied_filters.get('include_undated',False),
                          stale=[(d.path,d.source_info,d.view.to_json() if panel.built_respect else '') for d in panel.documents]!=[(d.path,d.source_info,d.view.to_json() if panel.built_respect else '') for d in reader.documents])
        ioc=self.window.ioc_panel;hunts=[copy.deepcopy(ioc.store.metadata)] if ioc.store else []
        persistence_error=self.persistence_error;state_path=str(self.state_path() or '');dropped=self.dropped;report_path=Path(state_path).with_name('coverage-last.json') if state_path else None;report_blocked=self.report_blocked
        wanted=copy.deepcopy(self.expected_tools)
        events=copy.deepcopy(self.events);verify=self.hashes.isChecked();expected=self.profile.currentData();deep=self.deep.isChecked();self.build_button.setEnabled(False)
        def work():
            collections=[active] if active else [];known={r.get('output') for r in collections};load_errors=[]
            if persistence_error:load_errors.append(event('Analyse','error',persistence_error,state_path))
            for path in paths:
                reader.check()
                try:
                    source=Path(path)
                    if source.stat().st_size>16*1024**2:raise ValueError('Inventaire limité à 16 Mio pour ce contrôle')
                    value=json.loads(source.read_text(encoding='utf-8'))
                    if value.get('format')!='fireblade-collection':raise ValueError('Format d’inventaire invalide')
                    if value.get('output') not in known:collections.append(value);known.add(value.get('output'))
                except Exception as exc:load_errors.append(event('Collecte','error',str(exc),path))
            result=audit(reader,collections=collections,timeline=timeline,hunts=hunts,events=events,verify_hashes=verify,expected=expected,expected_tools=wanted,deep_checks=deep,progress=self.progress.emit)
            result['findings'].extend(load_errors)
            result['counts']['error']+=len(load_errors);result['journal_dropped']=dropped
            if report_path and not report_blocked:
                try:save_report(report_path,result)
                except Exception as exc:
                    result['findings'].append(event('Analyse','error','Bilan non sauvegardé : '+str(exc),str(report_path)));result['counts']['error']+=1
            return result
        def release():self.reader=None;self.build_button.setEnabled(True)
        def done(result):
            release();self.report=result;self.stale=False
            counts=result['counts'];self.status.setText(f"Contrôle du {result['created']} · {len(result['sources'])} analyses · {counts['error']} erreurs · {counts['warning']} points à vérifier. "+('SHA-256 recalculés. ' if verify else 'SHA-256 non recalculés. ')+f'{self.dropped} anciennes opérations sorties du journal borné. '+self.persistence_error+' '+result['scope'])
            self.update_badge();self.filter()
        def failed(message='Contrôle interrompu ; le bilan précédent est conservé.'):
            release();self.status.setText(message);self.stale=True;self.update_badge()
        self.window.run(work,done,on_error=failed,on_cancel=failed,coverage_stage='Intégrité')
    def filter(self,*_):
        data=(self.report or {}).get('findings',[]) if self.mode.currentIndex()==0 else self.events
        severity=self.level.currentData();query=self.search.text().casefold()
        self.entries=[r for r in data if (not severity or r['severity']==severity) and (not query or query in json.dumps(r,ensure_ascii=False).casefold())]
        self.model.display([[r.get('stage',''),{'info':'Information','warning':'À vérifier','error':'Erreur'}.get(r.get('severity'),r.get('severity')),*[r.get(k,'') for k in ('path','reason','impact','action')]] for r in self.entries]);self.details.clear()
    def show_details(self,index):
        if index.isValid():
            item=self.entries[index.row()]
            self.details.setPlainText('\n\n'.join(label+' : '+str(item.get(key,'')) for label,key in [('Étape','stage'),('Fichier / périmètre','path'),('Cause','reason'),('Conséquence','impact'),('Action proposée','action')])+'\n\nMesures et références :\n'+json.dumps(item.get('metrics',{}),ensure_ascii=False,indent=2))
    def export(self):
        if not self.window.can_open_file():return
        self.ensure_context()
        if not self.report:self.status.setText('Lancez un contrôle avant d’exporter son bilan.');return
        path,_=QFileDialog.getSaveFileName(self,'Exporter le contrôle de couverture','couverture.json','JSON complet (*.json);;CSV des constats (*.csv)')
        if not path or not self.window.investigation_destination_is_safe(path):return
        report=copy.deepcopy(self.report);report.update(events=copy.deepcopy(self.events),stale=self.stale,journal_dropped=self.dropped)
        self.window.run(lambda:export_report(path,report),lambda _:self.window.statusBar().showMessage('Bilan de couverture exporté.'),coverage_stage='Export',coverage_context=path)
