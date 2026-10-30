"""Tabs hold small snapshots. Only the active tab owns a DuckDB connection."""
import base64
import json
import os
from pathlib import Path
import tempfile

from PySide6.QtWidgets import QFileDialog, QTabBar, QVBoxLayout, QWidget

from fireblade.core.engine import Case
from fireblade.core.models import AnalysisSnapshot, View


def write_session(path, snapshots, active):
    path = Path(path).resolve()
    payload = dict(format="fireblade-session", version=1, active=active, documents=[
        dict(path=s.path, source=s.source_info, view=json.loads(s.view.to_json()),
             header=base64.b64encode(s.header_state).decode("ascii")) for s in snapshots])
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, suffix=".partial", delete=False) as output:
            temporary = Path(output.name)
            json.dump(payload, output, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def read_session(path):
    path = Path(path)
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Session limitée à 4 Mo")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("format") != "fireblade-session" or payload.get("version") != 1:
        raise ValueError("Format de session Fireblade inconnu")
    documents = payload.get("documents")
    if not isinstance(documents, list) or not 1 <= len(documents) <= 100:
        raise ValueError("Une session doit contenir de 1 à 100 analyses")
    snapshots, seen = [], set()
    for doc in documents:
        target = Path(doc["path"])
        target = (path.parent / target).resolve() if not target.is_absolute() else target.resolve()
        if not target.is_file() or target in seen:
            raise ValueError(f"Analyse absente ou dupliquée : {target}")
        seen.add(target)
        view = View.from_json(json.dumps(doc["view"]))
        snapshots.append(AnalysisSnapshot(str(target), doc["source"], view,
                                         base64.b64decode(doc["header"], validate=True)))
    active = payload.get("active", 0)
    if type(active) is not int or not 0 <= active < len(snapshots):
        raise ValueError("Onglet actif invalide")
    return snapshots, active


class WorkspaceMixin:
    def setup_workspace(self):
        self.documents, self.active_document = [], -1
        content = self.takeCentralWidget()
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.tabs = QTabBar()
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
        while self.tabs.count():
            self.tabs.removeTab(0)
        for snapshot in self.documents:
            index = self.tabs.addTab(Path(snapshot.source_info["path"]).name)
            self.tabs.setTabToolTip(index, snapshot.path)
        self.tabs.setCurrentIndex(self.active_document)
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
            candidate = Case(snapshot.path, settings=self.settings)
            if candidate.info != snapshot.source_info:
                raise ValueError("Cette analyse a été remplacée par un autre jeu de données.")
            candidate.validate_view(snapshot.view)
        except Exception as exc:
            if candidate:
                candidate.close()
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
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Enregistrer la session", "enquete.fireblade-session", "Session Fireblade (*.fireblade-session)")
        if not path:
            return
        self.remember_active()
        try:
            target = Path(path).resolve()
            protected = {Path(s.path).resolve() for s in self.documents} | {Path(s.source_info["path"]).resolve() for s in self.documents}
            if target in protected:
                raise ValueError("La session ne peut pas écraser une analyse ou sa source.")
            write_session(target, self.documents, self.active_document)
            self.statusBar().showMessage("Session enregistrée : onglets, vues et dispositions des colonnes")
        except Exception as exc:
            self.error(exc)

    def load_session(self, path=None):
        if not self.can_open_file():
            return
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Ouvrir une session", "", "Session Fireblade (*.fireblade-session)")
        if not path:
            return
        candidate = None
        try:
            snapshots, active = read_session(path)
            # Validate every reference before replacing the current workspace.
            for snapshot in snapshots:
                if self.case and self.case.path == Path(snapshot.path):
                    existing = self.case
                    if existing.info != snapshot.source_info:
                        raise ValueError(f"Analyse remplacée : {snapshot.path}")
                    existing.validate_view(snapshot.view)
                else:
                    with_case = Case(snapshot.path, settings=self.settings)
                    try:
                        if with_case.info != snapshot.source_info:
                            raise ValueError(f"Analyse remplacée : {snapshot.path}")
                        with_case.validate_view(snapshot.view)
                    finally:
                        with_case.close()
            self.detach()
            self.documents, self.active_document = snapshots, -1
            self.sync_tabs()
            self.switch_document(active)
        except Exception as exc:
            if candidate:
                candidate.close()
            self.error(exc)
