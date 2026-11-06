"""Case-first entry and a separate worker pool for disk indexing."""
import json
import time
from datetime import datetime
from pathlib import Path
import uuid

from PySide6.QtCore import QObject, QThreadPool, QTimer, Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton,
    QVBoxLayout, QWidget)

from fireblade.core.models import AnalysisSnapshot, View
from fireblade.ui.language import source_text
from fireblade.ui.workers import Job


class DiskSignals(QObject):
    documents = Signal(object)


class DiskSourceDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('Analyser un disque')
        self.resize(650, 280)
        layout = QVBoxLayout(self)
        hint = QLabel('Lecture seule. Les artefacts reconnus sont copiés dans le case puis analysés. '
                      'Les résultats apparaissent progressivement. Le case doit être sur un autre volume. '
                      'Les fichiers supprimés ne sont pas récupérés.')
        hint.setWordWrap(True); layout.addWidget(hint)
        form = QFormLayout(); self.kind = QComboBox()
        for label, code in [('Disque logique / volume monté', 'mounted'),
                            ('Image disque RAW / E01', 'image'),
                            ('Disque physique (chemin de périphérique)', 'physical')]:
            self.kind.addItem(label, code)
        form.addRow('Source :', self.kind)
        row = QHBoxLayout(); self.path = QLineEdit(); row.addWidget(self.path, 1)
        browse = QPushButton('Parcourir…'); browse.clicked.connect(self.browse); row.addWidget(browse)
        form.addRow('Chemin :', row); layout.addLayout(form)
        note = QLabel('Disque physique : par exemple \\\\.\\PhysicalDrive1 sous Windows, /dev/sdb sous Linux. '
                      'Des droits administrateur peuvent être nécessaires. Un volume actif peut changer pendant la lecture ; '
                      'privilégiez une image acquise ou un support protégé en écriture.')
        note.setWordWrap(True); layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('Démarrer en arrière-plan')
        buttons.button(QDialogButtonBox.Ok).setEnabled(False)
        self.path.textChanged.connect(lambda t: buttons.button(QDialogButtonBox.Ok).setEnabled(bool(t.strip())))
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse(self):
        if self.kind.currentData() == 'mounted':
            path = QFileDialog.getExistingDirectory(self, 'Choisir le volume ou sa racine')
        else:
            path, _ = QFileDialog.getOpenFileName(self, 'Choisir une image disque', '',
                'Images disque (*.raw *.img *.dd *.E01 *.e01);;Tous les fichiers (*)')
        if path: self.path.setText(path)


class StartWorkflowMixin:
    def setup_start_workflow(self, require_case):
        self.require_case = require_case
        self.disk_job = None
        self.disk_collection = None
        self.disk_pool = QThreadPool(self); self.disk_pool.setMaxThreadCount(1)
        self.disk_signals = DiskSignals(self)
        self.disk_signals.documents.connect(self.receive_disk_documents)
        self._disk_pending = []
        self._analysis_origins = {}
        self.disk_drain = QTimer(self); self.disk_drain.setInterval(150)
        self.disk_drain.timeout.connect(self.drain_disk_documents)
        self.disk_status = QWidget(); row = QHBoxLayout(self.disk_status)
        row.setContentsMargins(0, 0, 0, 0)
        self.disk_label = QLabel(); self.disk_label.setTextFormat(Qt.PlainText)
        self.disk_label.setMaximumWidth(300)
        self.disk_progress = QProgressBar(); self.disk_progress.setFixedWidth(120)
        self.disk_stop = QPushButton('Arrêter'); self.disk_stop.clicked.connect(self.cancel_disk)
        row.addWidget(self.disk_label); row.addWidget(self.disk_progress); row.addWidget(self.disk_stop)
        self.statusBar().addPermanentWidget(self.disk_status)
        self.disk_status.hide()
        from PySide6.QtGui import QAction
        action = QAction('Analyser un disque…', self)
        action.triggered.connect(self.choose_disk)
        self.menuBar().actions()[0].menu().addAction(action)
        self.setup_organization()
        self.update_case_gate()

    def update_case_gate(self):
        if not hasattr(self, 'require_case'): return
        allowed = not self.require_case or self.active_investigation is not None
        for index in range(self.workbench.count()):
            self.workbench.setTabEnabled(index, allowed or index == self.cases_tab_index)
        if not allowed:
            self.workbench.setCurrentIndex(self.cases_tab_index)
        # Menu actions also have shortcuts, so disabling tabs alone is insufficient.
        for menu_action in self.menuBar().actions():
            menu = menu_action.menu()
            if menu is None: continue
            if source_text(menu_action).replace('&', '') in ('Fichier', 'Case'):
                permitted = {'Nouveau case…', 'Cases…', 'Quitter', 'Importer un case portable…'}
                for item in menu.actions():
                    if item.text() in permitted:
                        if item.property('caseGateEnabled'):
                            item.setEnabled(True); item.setProperty('caseGateEnabled', False)
                        continue
                    if not allowed:
                        if item.isEnabled(): item.setProperty('caseGateEnabled', True)
                        item.setEnabled(False)
                    elif item.property('caseGateEnabled'):
                        item.setEnabled(True); item.setProperty('caseGateEnabled', False)
            elif source_text(menu_action).replace('&', '') not in ('Aide', 'Affichage'):
                menu_action.setEnabled(allowed)
        if allowed and getattr(self, '_startup_file', None) is not None:
            source, self._startup_file = self._startup_file, None
            QTimer.singleShot(0, lambda: self.open_path(source))
        self.main_toolbar.setEnabled(allowed)
        # Adding data is how a session starts: this bar stays visible and usable
        # even before a case exists, otherwise "Parse a folder" is invisible.
        if hasattr(self, 'collection_toolbar'):
            self.collection_toolbar.setEnabled(True)
            self.collection_toolbar.setVisible(self.preferences.collection_toolbar_visible)
        self.main_toolbar.setVisible(self.preferences.main_toolbar_visible and (allowed or not self.require_case))
        workspace = getattr(self, 'workspace_layout', None)
        if workspace:
            workspace.toolbar.setEnabled(allowed)
            for _page, dock, *_rest in self.workbench.panels.values():dock.setEnabled(allowed)
            if allowed and workspace.pending_restore:workspace.restore()

    def require_active_case(self):
        if getattr(self, 'require_case', False) and self.active_investigation is None:
            self.show_investigations()
            self.statusBar().showMessage('Créez ou ouvrez un case avant de commencer.')
            return False
        return True

    def choose_disk(self):
        if not self.require_active_case() or not self.can_open_file(): return
        if self.disk_job is not None or self._folder_queue:
            self.statusBar().showMessage('Une indexation de disque est déjà en cours.'); return
        dialog = DiskSourceDialog(self)
        try:
            if dialog.exec() == QDialog.Accepted:
                self.start_disk_analysis(dialog.path.text().strip(), dialog.kind.currentData())
        finally:
            dialog.deleteLater()

    def start_disk_analysis(self, source, kind='mounted'):
        if not self.require_active_case() or self.active_investigation is None or self.disk_job is not None or self.disk_pool.activeThreadCount() or self._disk_pending or self._folder_queue:
            return False
        from fireblade.core.disk import DiskCollection
        # Validate the destination before creating any disk-work directory.
        parent = self.investigation_library.folder(self.active_investigation['id'])/'Disques'
        workspace = parent/(datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
        if kind == 'mounted':
            root = Path(source).resolve()
            if not root.is_dir() or root == workspace or root in workspace.parents:
                self.error('Choisissez un volume existant et stockez le case sur un autre volume.'); return False
        try:
            from dataclasses import replace
            settings = replace(self.settings, memory_mb=max(64, self.settings.memory_mb//2), threads=self.preferences.parsing_threads)
            collection = DiskCollection(source, workspace, self.toolpack(), settings,
                ready=self.disk_signals.documents.emit, source_kind=kind)
        except Exception as exc:
            self.error(exc); return False
        return self.start_background_collection(collection, workspace)

    def start_background_collection(self, collection, workspace=None):
        if self.disk_job is not None or self.disk_pool.activeThreadCount() or self._disk_pending:
            return False
        job = Job(collection.parse)
        collection.progress = job.signals.progress.emit
        self.disk_collection = collection
        label = ('Disque : '+collection.disk_source) if hasattr(collection, 'disk_source') else ('Dossier : '+str(collection.root))
        self.investigation_collections.append(dict(path=str(collection.output), name=label[:256]))
        self.refresh_investigation_collections()
        if not self.persist_investigation():
            self.investigation_collections = [item for item in self.investigation_collections if item['path'] != str(collection.output)]
            self.refresh_investigation_collections()
            import shutil
            if workspace is not None:shutil.rmtree(workspace)
            self.disk_collection = None
            return False
        self.disk_job = job
        self._background_final_received = False
        self._background_last_save = 0.0
        self.disk_drain.start()
        if not hasattr(collection, 'disk_source'):
            self.collection = collection
        self.disk_progress.setRange(0, 0)
        self.disk_stop.setEnabled(True); self.disk_status.show()
        self.disk_message('Découverte et indexation…')
        job.signals.progress.connect(self.disk_message)
        job.signals.done.connect(self.disk_finished)
        job.signals.error.connect(self.disk_failed)
        job.signals.cancelled.connect(self.disk_cancelled)
        self.workbench.setCurrentIndex(0)
        self.refresh_navigation()
        self.disk_pool.start(job)
        return True

    def disk_message(self, message):
        self.disk_label.setText(self.fontMetrics().elidedText(message, Qt.ElideMiddle, 290))
        self.disk_status.setToolTip(message)

    def cancel_disk(self):
        self._folder_queue.clear()
        if self.disk_job:
            self.disk_job.cancel()
            self.disk_collection.interrupt()
            self.disk_stop.setEnabled(False)
            self.disk_message('Arrêt demandé ; conservation des résultats terminés…')

    def receive_disk_documents(self, documents):
        self._disk_pending.extend(documents)

    def drain_disk_documents(self):
        if not self._disk_pending or not self.can_open_file(): return
        incoming, self._disk_pending = self._disk_pending[:16], self._disk_pending[16:]
        existing = {s.path for s in self.documents}
        for document in incoming:
            if document['path'] in existing: continue
            if len(self.documents) >= 1000:
                self.cancel_disk()
                self.disk_message('Limite de 1000 analyses ; résultats conservés sur disque.')
                break
            if document.get('navigation'):
                self._analysis_origins[document['path']] = document['navigation']
            self.documents.append(AnalysisSnapshot(document['path'], document['source'],
                View.from_json(json.dumps(document['view'])), b''))
            existing.add(document['path'])
        self.sync_tabs()
        # Never steal the current analysis when a later result arrives.
        if self.case is None and self.documents:
            self.switch_document(0)
        if time.monotonic()-self._background_last_save >= 1:
            self.persist_investigation(automatic=True)
            self._background_last_save = time.monotonic()

    def disk_cancelled(self):
        report = self.disk_collection.report
        report['status'] = 'cancelled'
        try:
            self.disk_collection.output.mkdir(parents=True, exist_ok=True)
            self.disk_collection.save()
        except OSError as exc:
            self.disk_failed('Arrêt demandé, mais le bilan n’a pas pu être enregistré : '+str(exc))
            return
        self.finish_disk(report)

    def disk_finished(self, report):
        self.finish_disk(report)

    def disk_failed(self, message):
        self.finish_disk(self.disk_collection.report, message)

    def finish_disk(self, report, error=None):
        # A disk may finish while a grid query or an exclusive import is active.
        # Wait for the workspace instead of saving/re-enabling controls mid-query.
        if not self.can_open_file():
            QTimer.singleShot(150, lambda: self.finish_disk(report, error))
            return
        self.disk_progress.setRange(0, 1)
        self.disk_progress.setValue(0 if error else 1)
        self.disk_stop.setEnabled(False)
        self.refresh_investigation_collections()
        if 'disk' not in report and not self._background_final_received:
            # Grouped outputs are published only when their final union is closed.
            self.receive_disk_documents(report['documents'])
            self.show_collection_report(report)
            self._background_final_received = True
        self.drain_disk_documents()
        if self._disk_pending:
            QTimer.singleShot(150, lambda: self.finish_disk(report, error))
            return
        self.coverage_panel.record_collection(report)
        self.persist_investigation(automatic=True)
        errors = len(report.get('disk', {}).get('errors', [])) + sum(e['status'] in ('error', 'attention', 'unsupported', 'no_output') for e in report['files'])
        label = 'Interrompu' if report['status'] == 'cancelled' else 'Terminé'
        if error:
            self.disk_message('Échec : '+error)
            self.coverage_notice('Disque', 'error', error, '')
        else:
            self.disk_message(f"{label} · {len(report['documents'])} analyses · {errors} incidents")
        self.disk_job = None
        self.disk_drain.stop()
        self.update_collection_controls()
        if self._folder_queue:
            if error or report['status'] == 'cancelled':self._folder_queue.clear()
            else:QTimer.singleShot(150, self.start_next_folder)

    def setup_organization(self):
        from PySide6.QtGui import QAction, QActionGroup
        menu = next(a.menu() for a in self.menuBar().actions()
                    if source_text(a).replace('&', '') == 'Affichage')
        organize = menu.addMenu('Organiser l’espace de travail')
        grouping = organize.addMenu('Regrouper l’arbre par')
        group = QActionGroup(self)
        for label, code in [('Disque → partition → dossiers', 'folders'),
                            ('Collecte → type d’artefact', 'families'), ('Liste des analyses par collecte', 'flat')]:
            action = QAction(label, self); action.setCheckable(True)
            action.setChecked(self.preferences.navigation_grouping == code)
            group.addAction(action); grouping.addAction(action)
            action.triggered.connect(lambda checked, value=code: self.set_navigation_option('navigation_grouping', value))
        position = organize.addMenu('Position de l’arbre')
        positions = QActionGroup(self)
        for label, code in [('À gauche', 'left'), ('À droite', 'right')]:
            action = QAction(label, self); action.setCheckable(True)
            action.setChecked(self.preferences.navigation_position == code)
            positions.addAction(action); position.addAction(action)
            action.triggered.connect(lambda checked, value=code: self.set_navigation_option('navigation_position', value))
        organize.addAction(self.navigation_action)
        organize.addAction(self.details_action)
        detail_positions = organize.addMenu('Position des détails de ligne')
        detail_group = QActionGroup(self)
        for label, code in [('En bas', 'bottom'), ('À droite', 'right'), ('En haut', 'top')]:
            action = detail_positions.addAction(label); action.setCheckable(True)
            action.setChecked(self.preferences.details_position == code); detail_group.addAction(action)
            action.triggered.connect(lambda checked, value=code: self.set_navigation_option('details_position', value))
        for label, expand in [('Déplier tout l’arbre', True), ('Replier tout l’arbre', False)]:
            action = organize.addAction(label)
            action.triggered.connect(self.navigator.tree.expandAll if expand else self.navigator.tree.collapseAll)
        toolbars = organize.addMenu('Barres d’outils')
        for toolbar in (self.main_toolbar, self.collection_toolbar):
            toolbars.addAction(toolbar.toggleViewAction())
        animate = organize.addAction('Animation au démarrage')
        animate.setCheckable(True); animate.setChecked(self.preferences.startup_animation)
        animate.toggled.connect(lambda value: self.set_navigation_option('startup_animation', value))
        self.details_action.setChecked(self.preferences.workspace_details_visible)
        self.details.setVisible(self.preferences.workspace_details_visible)
        self.details_action.toggled.connect(lambda value: self.set_navigation_option('workspace_details_visible', value))
        self.main_toolbar.setVisible(self.preferences.main_toolbar_visible)
        self.collection_toolbar.setVisible(self.preferences.collection_toolbar_visible)
        self.main_toolbar.toggleViewAction().triggered.connect(lambda value: self.set_navigation_option('main_toolbar_visible', value))
        self.collection_toolbar.toggleViewAction().triggered.connect(lambda value: self.set_navigation_option('collection_toolbar_visible', value))
        self.navigation_action.setChecked(self.preferences.navigation_visible)
        self.navigation_action.toggled.connect(lambda value: self.set_navigation_option('navigation_visible', value))
        self.apply_navigation_organization()

    def apply_navigation_organization(self):
        if not hasattr(self, 'navigator'): return
        workspace = getattr(self, 'workspace_layout', None)
        if workspace and 'artifacts' in workspace.auxiliary:
            self.addDockWidget(Qt.LeftDockWidgetArea if self.preferences.navigation_position == 'left' else Qt.RightDockWidgetArea,
                               workspace.auxiliary['artifacts'][0])
            self.refresh_navigation();return
        sizes = self.workspace_splitter.sizes()
        old_index = self.workspace_splitter.indexOf(self.navigator)
        width = sizes[old_index] if sizes and old_index >= 0 else 230
        self.workspace_splitter.insertWidget(0 if self.preferences.navigation_position == 'left' else 1, self.navigator)
        self.workspace_splitter.setStretchFactor(self.workspace_splitter.indexOf(self.navigator), 0)
        self.workspace_splitter.setStretchFactor(1-self.workspace_splitter.indexOf(self.navigator), 1)
        self.workspace_splitter.setSizes([max(width, 180), max(self.width()-width, 400)] if self.preferences.navigation_position == 'left'
                                        else [max(self.width()-width, 400), max(width, 180)])
        self.refresh_navigation()

    def set_navigation_option(self, name, value):
        from fireblade.core.preferences import save_preferences
        previous = getattr(self.preferences, name)
        setattr(self.preferences, name, value)
        try:
            save_preferences(self.preferences)
        except (OSError, ValueError) as exc:
            setattr(self.preferences, name, previous)
            self.error(exc)
        if name == 'details_position':
            self.apply_preferences()
        self.apply_navigation_organization()
