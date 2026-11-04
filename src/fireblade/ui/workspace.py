"""Tabs hold small snapshots. Only the active tab owns a DuckDB connection."""
import json
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QVBoxLayout, QWidget, QSplitter
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

from fireblade.core.engine import Case
from fireblade.core.models import AnalysisSnapshot, View
from fireblade.ui.workspace_tabs import WorkspaceTabs


from fireblade.core.sessions import read_session, write_session


class WorkspaceMixin:
    def setup_workspace(self):
        self.documents, self.active_document = [], -1
        self.closed_documents = []
        self._analysis_labels = {}
        content = self.takeCentralWidget()
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.tabs = WorkspaceTabs()
        self.tabs.setExpanding(False)
        self.tabs.setTabsClosable(True)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.currentChanged.connect(self.switch_document)
        self.tabs.tabCloseRequested.connect(self.close_document)
        body = QWidget();body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0,0,0,0);body_layout.setSpacing(0)
        body_layout.addWidget(self.tabs);body_layout.addWidget(content)
        from fireblade.ui.navigation import AnalysisNavigator
        self.navigator = AnalysisNavigator()
        self.navigator.activated.connect(self.switch_document)
        self.workspace_splitter = QSplitter(Qt.Horizontal)
        self.workspace_splitter.addWidget(self.navigator)
        self.workspace_splitter.addWidget(body)
        self.workspace_splitter.setStretchFactor(1,1)
        self.workspace_splitter.setSizes([210,1000])
        layout.addWidget(self.workspace_splitter)
        self.navigation_action = QAction('Navigation des analyses',self)
        self.navigation_action.setCheckable(True);self.navigation_action.setChecked(True)
        self.navigation_action.toggled.connect(lambda _:self.refresh_navigation())
        self.navigator.close_requested.connect(lambda:self.navigation_action.setChecked(False))
        view_menu = next(a.menu() for a in self.menuBar().actions() if a.text().replace('&','')=='Affichage')
        view_menu.addAction(self.navigation_action)
        self.setCentralWidget(wrapper)
        self.tabs.hide()
        self.refresh_navigation()

    def refresh_navigation(self):
        if not hasattr(self,'navigator'):return
        collections = list(getattr(self,'investigation_collections',[]))
        current = getattr(self,'collection',None)
        if current and not any(c['path']==str(current.output) for c in collections):
            collections.append(dict(path=str(current.output),name=current.root.name))
        if current:
            for context in current.report.get('contexts',[]):
                self._analysis_labels[context['analysis']]=str(context['rule'])[:120]+' · ± '+str(context['minutes'])+' min'
        origins = dict(getattr(self, '_analysis_origins', {}))
        # Read saved provenance only once per collection, never open inactive databases.
        cache = getattr(self, '_navigation_origin_cache', {})
        for item in collections:
            path = item['path']
            if path not in cache:
                try:
                    report = Path(path)/'collection.json'
                    if report.is_file() and report.stat().st_size < 32*1024*1024:
                        data = json.loads(report.read_text(encoding='utf-8'))
                        cache[path] = {d['path']: d['navigation'] for d in data.get('documents', []) if d.get('navigation')}
                except (OSError, ValueError, KeyError):
                    cache[path] = {}
            origins.update(cache.get(path, {}))
        origins.update(getattr(self, '_analysis_origins', {}))
        self._navigation_origin_cache = cache
        self.navigator.refresh(self.documents,self.active_document,collections,self._analysis_labels,origins,
            getattr(getattr(self, 'preferences', None), 'navigation_grouping', 'folders'))
        self.update_navigation_visibility()

    def update_navigation_visibility(self, *_):
        if not hasattr(self,'navigator'):return
        preview=getattr(self,'context_preview',None)
        compact=preview is not None and preview.isVisible() and self.width()<1100
        self.navigator.setVisible((bool(self.documents) or getattr(self, "disk_job", None) is not None) and self.navigation_action.isChecked() and not compact)

    def remember_active(self):
        snapshot = self.snapshot_analysis()
        if snapshot is not None and 0 <= self.active_document < len(self.documents):
            self.documents[self.active_document] = snapshot

    def sync_tabs(self):
        self.tabs.blockSignals(True)
        self.tabs.replace_documents([Path(s.source_info["path"]).name for s in self.documents],
                                    [s.path for s in self.documents], self.active_document)
        self.tabs.setVisible(bool(self.documents))
        self.tabs.blockSignals(False)
        self.refresh_navigation()

    def track_case(self):
        snapshot = self.snapshot_analysis()
        index = next((i for i, s in enumerate(self.documents) if s.path == snapshot.path), -1)
        if index < 0:
            self.documents.append(snapshot)
            index = len(self.documents) - 1
        else:
            self.documents[index] = snapshot
        self.active_document = index
        self.sync_tabs()

    def switch_document(self, index):
        if not 0 <= index < len(self.documents):
            return
        snapshot = self.documents[index]
        if self.case and str(self.case.path) == snapshot.path and self.model:
            return
        if not self.can_open_file():
            self.sync_tabs()
            return
        candidate = None
        try:
            if not Path(snapshot.path).is_file():
                raise FileNotFoundError(f"Analyse introuvable : {snapshot.path}")
            candidate = self.connection_work(lambda: Case(snapshot.path, settings=self.settings))
            if candidate.info != snapshot.source_info:
                raise ValueError("Cette analyse a été remplacée par un autre jeu de données.")
            candidate.validate_view(snapshot.view)
        except Exception as exc:
            if candidate:
                self.connection_work(candidate.close)
            self.sync_tabs()
            self.error(exc)
            return
        self.detach()
        self.attach(candidate, snapshot.view, snapshot.header_state)

    def close_document(self, index):
        if not 0 <= index < len(self.documents) or not self.can_open_file():
            return
        active_path = str(self.case.path) if self.case else None
        removing_active = self.documents[index].path == active_path
        if removing_active:
            self.detach()
        self.closed_documents.append(self.documents[index])
        self.closed_documents = self.closed_documents[-20:]
        del self.documents[index]
        self.active_document = next((i for i, s in enumerate(self.documents) if s.path == active_path), -1)
        self.sync_tabs()
        if removing_active and self.documents:
            self.switch_document(min(index, len(self.documents) - 1))

    def next_document(self, direction=1):
        if self.documents:
            self.switch_document((self.active_document + direction) % len(self.documents))

    def save_session(self, path=None):
        if not self.can_open_file() or not self.documents:
            return
        if not path and getattr(self,'active_investigation',None) is not None:
            return self.save_investigation()
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Enregistrer la session", "enquete.fireblade-session", "Session Fireblade (*.fireblade-session)")
        if not path:
            return
        if not self.export_destination_is_safe(path):return False
        self.remember_active()
        try:
            target = Path(path).resolve()
            write_session(target, self.documents, self.active_document)
            if getattr(self,'active_investigation',None) is not None:
                if not self.persist_investigation():return False
            self.statusBar().showMessage("Session enregistrée : onglets, vues et dispositions des colonnes")
        except Exception as exc:
            self.error(exc)

    def validate_session(self, path):
        snapshots, active = read_session(path)
        self.validate_session_snapshots(snapshots)
        return snapshots, active

    def prepare_snapshot(self, snapshot):
        candidate = self.connection_work(lambda: Case(snapshot.path, settings=self.settings))
        try:
            if candidate.info != snapshot.source_info:
                raise ValueError(f"Analyse remplacée : {snapshot.path}")
            candidate.validate_view(snapshot.view)
            return candidate
        except BaseException:
            self.connection_work(candidate.close)
            raise

    def validate_session_snapshots(self, snapshots):
        for snapshot in snapshots:
            if self.case and self.case.path == Path(snapshot.path):
                if self.case.info != snapshot.source_info:
                    raise ValueError(f"Analyse remplacée : {snapshot.path}")
                self.case.validate_view(snapshot.view)
            else:
                candidate = self.prepare_snapshot(snapshot)
                self.connection_work(candidate.close)

    def install_session_snapshots(self, snapshots, active):
        candidate = self.prepare_snapshot(snapshots[active])
        try:
            self.detach()
            self.documents, self.active_document = list(snapshots), -1
            self.sync_tabs()
            snapshot=snapshots[active]
            self.attach(candidate,snapshot.view,snapshot.header_state,auto_layout=False)
        except BaseException:
            if self.case is not candidate:self.connection_work(candidate.close)
            raise

    def load_session(self, path=None):
        if not self.can_open_file():
            return
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Ouvrir une session", "", "Session Fireblade (*.fireblade-session)")
        if not path:
            return
        candidate = None
        try:
            snapshots, active = self.validate_session(path)
            self.install_session_snapshots(snapshots,active)
            return True
        except Exception as exc:
            if candidate:
                self.connection_work(candidate.close)
            self.error(exc)
            return False
