"""Collection import and offline detection controls."""
from collections import Counter
from datetime import datetime
from pathlib import Path
import uuid

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QPalette
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QRadioButton, QFileDialog, QHBoxLayout, QLabel, QPushButton, QTabWidget, QVBoxLayout, QWidget

from fireblade.core.collection import Collection, ToolPack
from fireblade.ui.alert_context import AlertContextMixin
from fireblade.runtime.resources import resource_path
from fireblade.runtime.windows_paths import user_directory


class CollectionOrganizationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Organiser les résultats de la collecte')
        self.resize(570, 260)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Comment souhaitez-vous consulter les résultats ?'))
        self.artifacts = QRadioButton('Un onglet par type d’artefact ou famille CatScale')
        self.artifacts.setChecked(True)
        layout.addWidget(self.artifacts)
        separate = QLabel('Onglets : [Amcache] [EVTX] [Shellbags]…\nCatScale : [Processus et réseau] [Persistance]…\nLes résultats du même type sont réunis.')
        separate.setWordWrap(True)
        layout.addWidget(separate)
        self.combined = QRadioButton('Tout dans un seul onglet, regroupé par artefact ou famille CatScale')
        layout.addWidget(self.combined)
        merged = QLabel('Une grille : Artefact → EVTX / Amcache / Shellbags…\nLes groupes sont déjà créés. Chaque ligne conserve son fichier source ; les colonnes propres à chaque format restent disponibles.')
        merged.setWordWrap(True)
        layout.addWidget(merged)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('Importer et parser')
        buttons.button(QDialogButtonBox.Cancel).setText('Annuler')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def organization(self):
        return 'combined' if self.combined.isChecked() else 'artifacts'


class CollectionMixin(AlertContextMixin):
    def setup_collection(self):
        self.collection = None
        self.workbench = QTabWidget()
        workspace = self.takeCentralWidget()
        workspace.setAutoFillBackground(True)
        workspace.setBackgroundRole(QPalette.Window)
        self.workbench.addTab(workspace, 'Analyses')
        panel = QWidget()
        layout = QVBoxLayout(panel)
        title = QLabel('1. Importer et parser')
        title.setStyleSheet('font-size: 18px; font-weight: bold;')
        layout.addWidget(title)
        explanation = QLabel('Choisissez un dossier d’artefacts Windows ou une collecte Linux CatScale (dossier extrait ou archives catscale_*.tar.gz). Les moteurs intégrés produisent des résultats séparés, puis Fireblade les ouvre dans une session. Hayabusa analyse uniquement les EVTX Windows inventoriés et ajoute un onglet Alertes.')
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        row = QHBoxLayout()
        for label, callback in [('Choisir un dossier et parser…', self.parse_collection),
                                ('Reprendre une collecte…', self.reopen_collection)]:
            control = QPushButton(label)
            control.clicked.connect(callback)
            row.addWidget(control)
        layout.addLayout(row)
        layout.addWidget(QLabel('2. Détecter dans les EVTX Windows'))
        settings = QHBoxLayout()
        settings.addWidget(QLabel('Gravité minimale Hayabusa :'))
        self.hayabusa_level = QComboBox()
        for label, code in [('Information', 'informational'), ('Faible', 'low'), ('Moyenne', 'medium'), ('Élevée', 'high'), ('Critique', 'critical')]:
            self.hayabusa_level.addItem(label, code)
        self.hayabusa_level.setCurrentIndex(1)
        settings.addWidget(self.hayabusa_level)
        self.hayabusa_button = QPushButton('Analyser avec Hayabusa')
        self.hayabusa_button.clicked.connect(self.analyze_collection)
        settings.addWidget(self.hayabusa_button)
        settings.addStretch()
        layout.addLayout(settings)
        self.hayabusa_hint = QLabel();self.hayabusa_hint.setTextFormat(Qt.PlainText);self.hayabusa_hint.setWordWrap(True)
        layout.addWidget(self.hayabusa_hint)
        from fireblade.ui.collection_report import CollectionReport
        self.collection_report = CollectionReport()
        layout.addWidget(self.collection_report, 1)
        self.workbench.addTab(panel, 'Collecte et détection')
        self.setCentralWidget(self.workbench)
        file_menu = self.menuBar().actions()[0].menu()
        action = QAction('Importer un dossier de collecte…', self)
        action.triggered.connect(self.parse_collection)
        file_menu.insertAction(file_menu.actions()[1], action)
        analyze = self.hayabusa_action = QAction('Analyser la collecte avec Hayabusa', self)
        analyze.triggered.connect(self.analyze_collection)
        menu = next(a.menu() for a in self.menuBar().actions() if a.text().replace('&', '') == 'Analyse')
        menu.addAction(analyze)
        toolbar = self.addToolBar('Collecte')
        toolbar.addAction(action)
        # Detection belongs to the EVTX step, not the global file toolbar.
        help_menu = next(a.menu() for a in self.menuBar().actions() if a.text().replace('&','')=='Aide')
        sources = help_menu.addAction('Exporter les sources Hayabusa…')
        sources.triggered.connect(self.export_hayabusa_source)
        self.show_collection_report()
        self.setup_alert_context()

    def toolpack(self):
        return ToolPack(resource_path('forensic-tools'))

    def show_collection_report(self, report=None):
        pack = self.toolpack()
        from fireblade.core.collection import PARSERS
        ready = [name for name in (*PARSERS, 'Shellbags', 'Hayabusa') if pack.available(name)]
        names = {'pending':'En attente', 'running':'En cours', 'complete':'Terminé',
                 'complete_with_warnings':'Terminé avec avertissements', 'unsupported':'Non reconnu',
                 'skipped':'Ignoré', 'error':'Erreur', 'cancelled':'Interrompu',
                 'attention':'À vérifier', 'no_output':'Aucune sortie', 'companion':'Journal de transaction'}
        status = lambda value: names.get(value, value)
        lines = ['Parsers intégrés : CatScale Linux et WebCache ESE (lecture seule).', 'Moteurs Windows disponibles : '+(', '.join(ready) or 'aucun pack intégré dans cette construction')]
        if report:
            organization = {'files':'Un onglet par résultat', 'artifacts':'Un onglet par artefact', 'combined':'Onglet unique regroupé par artefact'}.get(report.get('organization', 'files'), '')
            lines += ['', 'Organisation : '+organization, 'Dossier source : '+report['source'], 'Dossier de travail : '+report['output'],
                      'État de l’import : '+status(report['status']), 'Bilan : '+str(dict(Counter(status(e['status']) for e in report['files']))),
                      'Analyses chargées : '+str(len(report['documents']))]
            if report.get('detection'):
                lines += ['Hayabusa : '+status(report['detection']['status']), str(report['detection'].get('error', ''))]
            for entry in report['files']:
                lines.append(f"{status(entry['status'])} · {entry['path']}")
                if entry.get('sha256'):lines.append('  SHA-256 : '+entry['sha256'])
                if entry.get('error'):lines.append('  '+entry['error'])
                for run in entry.get('runs', []):
                    lines.append('  '+run['tool']+' : '+status(run['status'])+' '+run.get('error', ''))
                    lines.extend('    '+warning for warning in run.get('warnings', [])[:10])
                    for member in run.get('catscale',{}).get('members',[]):
                        if member['status'] in ('error','unsupported','skipped'):
                            lines.append('    '+member['status']+' · '+member['path']+' : '+member.get('reason',''))
        lines += ['', 'Un fichier non reconnu, un moteur absent ou une erreur restent dans le bilan. Une alerte est une piste à vérifier, pas une conclusion de compromission. Les résultats et journaux sont conservés dans le dossier de travail.']
        self.collection_report.set_report(report, '\n'.join(lines))
        self.update_collection_controls()
        self.refresh_navigation()

    def update_collection_controls(self):
        if not hasattr(self,'hayabusa_action'):return
        report=self.collection.report if self.collection else None
        evtx=bool(report and any('EvtxECmd' in e.get('tools',[]) and e['status'] in ('complete','complete_with_warnings') for e in report['files']))
        ready=evtx and report['status'] not in ('pending','running') and not self.busy
        self.hayabusa_action.setEnabled(ready);self.hayabusa_button.setEnabled(ready)
        self.hayabusa_level.setEnabled(ready)
        reason=('Attendez la fin du traitement en cours.' if self.busy else
                'Importez une collecte pour activer la détection.' if report is None else
                'Hayabusa nécessite des EVTX parsés ; les textes CatScale se consultent dans Analyses.' if not evtx else
                'EVTX disponibles. Choisissez le seuil puis lancez la détection.')
        detection=report.get('detection') if report else None
        if detection and detection.get('status')!='running':
            reason+=' Dernière détection : '+str(detection.get('alerts',0))+' alerte(s) · '+str(detection['status'])
        self.hayabusa_hint.setText(reason)
        self.hayabusa_action.setToolTip(reason)

    def collection_finished(self, report):
        self.show_collection_report(report)
        self.workbench.setCurrentIndex(1)
        if not report['documents']:return
        collection=self.collection
        epoch=self._workspace_epoch
        self._collection_open_pending=True
        self.centralWidget().setEnabled(False)
        self.set_file_actions(False)
        def open_results():
            if self.pool.activeThreadCount():
                QTimer.singleShot(20,open_results)
                return
            try:
                if self.collection is not collection or self._workspace_epoch!=epoch:return
                from fireblade.core.sessions import read_session,write_session
                self.remember_active()
                if self.documents:
                    write_session(collection.output/'previous-workspace.fireblade-session',self.documents,self.active_document)
                incoming,active=read_session(collection.output/'collection.fireblade-session')
                snapshots=incoming
                if getattr(self,'active_investigation',None) is not None:
                    existing={snapshot.path for snapshot in self.documents}
                    snapshots=list(self.documents)+[snapshot for snapshot in incoming if snapshot.path not in existing]
                if len(snapshots)>1000:
                    raise ValueError('Le case dépasserait 1000 analyses. Les résultats restent dans le dossier de collecte.')
                wanted=(report.get('detection') or {}).get('analysis') or incoming[active].path
                selected=next(i for i,snapshot in enumerate(snapshots) if snapshot.path==wanted)
                self.validate_session_snapshots(snapshots)
                self.install_session_snapshots(snapshots,selected)
                if (report.get('detection') or {}).get('outputs'):
                    self.select_evidence_row(str(self.case.path),1)
                self.workbench.setCurrentIndex(0)
                if getattr(self,'active_investigation',None) is not None:
                    self.remember_investigation_collection()
                    self.persist_investigation()
            except Exception as exc:self.error(exc)
            finally:
                self._collection_open_pending=False
                self.centralWidget().setEnabled(not self.busy)
                self.set_file_actions(self.model is not None and not self.busy)
        QTimer.singleShot(0,open_results)

    def start_collection_job(self, function):
        self.workbench.setCurrentIndex(1)
        def failed(message):
            self.show_collection_report(self.collection.report)
            self.collection_report.setPlainText(self.collection_report.toPlainText()+'\nErreur : '+message)
            self.workbench.setCurrentIndex(1)
            self.error(message)
        job = self.run(function, self.collection_finished, exclusive=True, on_error=failed)
        if job is not None:
            self.collection.progress = job.signals.progress.emit
        self.cancel_action.setEnabled(True)

    def parse_collection(self):
        if not self.can_open_file():return
        path = QFileDialog.getExistingDirectory(self, 'Dossier contenant les artefacts forensic')
        if not path:return
        dialog = CollectionOrganizationDialog(self)
        accepted = dialog.exec()
        organization = dialog.organization()
        dialog.deleteLater()
        if accepted != QDialog.DialogCode.Accepted:return
        parent = self.investigation_data_directory('Collectes') or user_directory()/'Collectes'
        parent.mkdir(parents=True, exist_ok=True)
        output = parent/(datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
        try:
            self.collection = Collection(path, output, self.toolpack(), self.settings, organization=organization)
            self.start_collection_job(self.collection.parse)
        except (OSError, ValueError) as exc:
            self.error(exc)

    def reopen_collection(self):
        if not self.can_open_file():return
        path = QFileDialog.getExistingDirectory(self, 'Dossier de travail contenant collection.json')
        if not path:return
        try:
            self.collection = Collection.reopen(path, self.toolpack(), self.settings)
            self.collection_finished(self.collection.report)
        except Exception as exc:self.error(exc)

    def analyze_collection(self):
        if not self.can_open_file():return
        if self.collection is None:
            self.workbench.setCurrentIndex(1)
            self.statusBar().showMessage('Importez ou reprenez une collecte avant l’analyse Hayabusa.')
            return
        if not any('EvtxECmd' in entry.get('tools',[]) for entry in self.collection.report['files']):
            self.workbench.setCurrentIndex(1)
            self.statusBar().showMessage('Hayabusa nécessite des EVTX Windows. Les données CatScale se consultent dans les onglets d’analyse.')
            return
        self.remember_collection_views()
        level = self.hayabusa_level.currentData()
        self.start_collection_job(lambda: self.collection.analyze(level))

    def remember_collection_views(self):
        import base64
        import json
        self.remember_active()
        snapshots = {snapshot.path: snapshot for snapshot in self.documents}
        for document in self.collection.report['documents']:
            snapshot = snapshots.get(document['path'])
            if snapshot is not None:
                document['view'] = json.loads(snapshot.view.to_json())
                document['header'] = base64.b64encode(snapshot.header_state).decode('ascii')
        self.collection.save()

    def export_hayabusa_source(self):
        import shutil
        source = resource_path('forensic-tools/Hayabusa-source.zip')
        if not source.is_file():
            self.error('Sources Hayabusa absentes de cette construction.')
            return
        target, _ = QFileDialog.getSaveFileName(self, 'Exporter les sources Hayabusa', 'Hayabusa-source.zip', 'ZIP (*.zip)')
        if target:
            try:
                shutil.copyfile(source, target)
                self.statusBar().showMessage('Sources Hayabusa exportées : '+target)
            except OSError as exc:self.error(exc)
