"""Tabs hold small snapshots. Only the active tab owns a DuckDB connection."""
import json
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QVBoxLayout, QWidget

from fireblade.core.engine import Case
from fireblade.core.models import AnalysisSnapshot, View
from fireblade.ui.workspace_tabs import WorkspaceTabs


from fireblade.core.sessions import read_session, write_session


class WorkspaceMixin:
    def setup_workspace(self):
        self.documents, self.active_document = [], -1
        self.closed_documents = []
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
        layout.addWidget(self.tabs)
        layout.addWidget(content)
        self.setCentralWidget(wrapper)
        self.tabs.hide()

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
        self.remember_active()
        try:
            target = Path(path).resolve()
            protected = {Path(s.path).resolve() for s in self.documents} | {Path(s.source_info["path"]).resolve() for s in self.documents}
            from fireblade.core.paths import protected_destination
            if protected_destination(target,protected):
                raise ValueError("La session ne peut pas écraser une analyse ou sa source.")
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
