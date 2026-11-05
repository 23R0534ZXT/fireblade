"""Sequential cross-document search, one extra disk connection at most."""
from dataclasses import dataclass, field
from pathlib import Path
import copy
import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)
from fireblade.core.engine import Case
from fireblade.core.errors import OperationCancelled, job_cancelled
from fireblade.core.models import View

SAMPLE_ROWS = 4
SAMPLE_WIDTH = 160


def summarize(row, limit=SAMPLE_WIDTH):
    """One readable line for a matching row, enough to recognise the event."""
    values = [str(value) for value in row[1:] if value not in (None, '')]
    return (' · '.join(values))[:limit]


@dataclass
class SearchHit:
    path: str
    name: str
    count: int | None
    error: str = ""
    sample: list = field(default_factory=list)


class WorkspaceSearch:
    def __init__(self, documents, settings, active=None):
        self.documents = copy.deepcopy(documents)
        self.settings, self.active = settings, active
        self.lock = threading.Lock()
        self.current = None
        self.cancelled = threading.Event()

    def interrupt(self):
        self.cancelled.set()
        with self.lock:
            if self.current:
                self.current.interrupt()

    def find(self, text, respect_filters=False):
        if not text.strip():
            raise ValueError("Saisissez un texte à rechercher")
        results = []
        for document in self.documents:
            if self.cancelled.is_set() or job_cancelled():
                raise OperationCancelled()
            case = None
            own = self.active is None or str(self.active.path) != document.path
            try:
                if not Path(document.path).is_file():
                    raise FileNotFoundError("Analyse introuvable")
                case = Case(document.path, settings=self.settings, read_only=True) if own else self.active
                if case.info != document.source_info:
                    raise ValueError("L’analyse a été remplacée")
                with self.lock:
                    self.current = case
                    if self.cancelled.is_set():
                        raise OperationCancelled()
                view = copy.deepcopy(document.view) if respect_filters else View()
                view.search = text
                count = case.count(view)
                sample = []
                if count:
                    # A few real rows, so the panel shows events and not a number.
                    sample = [summarize(row) for row in case.page(view, limit=SAMPLE_ROWS)]
                results.append(SearchHit(document.path, Path(document.source_info['path']).name, count, sample=sample))
            except OperationCancelled:
                raise
            except Exception as exc:
                results.append(SearchHit(document.path, Path(document.source_info['path']).name, None, str(exc)))
            finally:
                with self.lock:
                    self.current = None
                    if own and case:
                        case.close()
        return results


class SearchDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("Rechercher dans toutes les analyses")
        self.resize(740, 400)
        self.results, self.task = [], None
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.text = QLineEdit()
        self.text.setPlaceholderText("Texte à rechercher dans tous les fichiers ouverts")
        self.search = QPushButton("Rechercher")
        self.stop = QPushButton("Interrompre")
        self.stop.setEnabled(False)
        self.search.clicked.connect(self.start)
        self.text.returnPressed.connect(self.start)
        self.stop.clicked.connect(self.cancel)
        row.addWidget(self.text, 1)
        row.addWidget(self.search)
        row.addWidget(self.stop)
        layout.addLayout(row)
        self.filters = QCheckBox("Respecter les filtres et signets de chaque analyse")
        layout.addWidget(self.filters)
        self.only_matches = QCheckBox('Correspondances uniquement');self.only_matches.setChecked(True)
        self.only_matches.toggled.connect(self.filter_results);layout.addWidget(self.only_matches)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Fichier", "Correspondances", "État"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self.open_result)
        layout.addWidget(self.table)
        from PySide6.QtGui import QFontDatabase
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.details.setMinimumHeight(56)
        self.table.currentCellChanged.connect(lambda *_args: self.show_sample())
        layout.addWidget(self.details)
        self.message = QLabel("Double-cliquez un résultat pour ouvrir l’analyse filtrée.")
        layout.addWidget(self.message)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)

    def cancel(self):
        if self.task:
            self.task.interrupt()

    def finished(self):
        self.task = None
        self.search.setEnabled(True)
        self.stop.setEnabled(False)
        self.text.setEnabled(True)
        self.filters.setEnabled(True)

    def start(self):
        if self.task or not self.text.text().strip() or not self.window.can_open_file():
            return
        self.window.remember_active()
        self.task = WorkspaceSearch(self.window.documents, self.window.settings, self.window.case)
        self.window.workspace_search = self.task
        self.query, self.respect = self.text.text(), self.filters.isChecked()
        self.search.setEnabled(False)
        self.stop.setEnabled(True)
        self.text.setEnabled(False)
        self.filters.setEnabled(False)
        self.message.setText("Recherche sur disque…")
        task = self.task
        def done(results):
            self.finished()
            self.results = results
            self.table.setRowCount(len(results))
            for row, result in enumerate(results):
                for col, value in enumerate((result.name, str(result.count) if result.count is not None else "—", result.error or "Terminé")):
                    item = QTableWidgetItem(value)
                    item.setToolTip(result.path if col == 0 else result.error)
                    self.table.setItem(row, col, item)
            self.filter_results()
            self.message.setText(f"{sum(r.count or 0 for r in results)} correspondances · {len(results)} artefacts parcourus")
            if results:
                self.table.setCurrentCell(0, 0)
            self.show_sample()
        def failed(message="Recherche interrompue"):
            self.finished()
            self.message.setText(message)
        self.window.run(lambda: task.find(self.query, self.respect), done, on_cancel=failed, on_error=failed)

    def filter_results(self):
        for row, result in enumerate(self.results):
            self.table.setRowHidden(row, self.only_matches.isChecked() and result.count == 0 and not result.error)

    def show_sample(self):
        """Show a few real matching rows for the selected artifact."""
        row = self.table.currentRow()
        if not 0 <= row < len(self.results):
            self.details.setText("")
            return
        result = self.results[row]
        if result.error:
            self.details.setText(result.error)
            return
        if not result.sample:
            self.details.setText("Aucune correspondance dans cet artefact.")
            return
        lines = [f"• {line}" for line in result.sample]
        more = (result.count or 0) - len(result.sample)
        if more > 0:
            lines.append(f"… et {more:,} autres correspondances".replace(",", " "))
        self.details.setText("\n".join(lines))

    def open_result(self, row, _column):
        if self.task or not 0 <= row < len(self.results) or not self.window.can_open_file():
            return
        result = self.results[row]
        if result.error:
            self.message.setText(result.error)
            return
        index = next((i for i, doc in enumerate(self.window.documents) if doc.path == result.path), -1)
        if index < 0:
            return
        self.window.switch_document(index)
        if self.window.case and str(self.window.case.path) == result.path:
            view = copy.deepcopy(self.window.view) if self.respect else View()
            view.search = self.query
            self.window.set_view(view)
            self.accept()

    def reject(self):
        if self.task:
            self.cancel()
            self.message.setText("Annulation en cours…")
            return
        super().reject()
