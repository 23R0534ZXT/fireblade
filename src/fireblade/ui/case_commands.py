"""Window commands that span a case: the client report and the destruction of evidence."""

from __future__ import annotations

import base64
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from fireblade.core import case_workspace, client_report, destruction
from fireblade.core.model_texts import ACTION_TYPE_LABELS


class ClientReportDialog(QDialog):
    def __init__(self, parent=None, default_title="", analyst=""):
        super().__init__(parent)
        self.setWindowTitle("Rapport client")
        self.resize(520, 300)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.title = QLineEdit(default_title)
        self.analyst = QLineEdit(analyst)
        form.addRow("Titre :", self.title)
        form.addRow("Analyste :", self.analyst)
        layout.addLayout(form)
        self.graph = QCheckBox("Inclure le graphe d'attaque")
        self.graph.setChecked(True)
        layout.addWidget(self.graph)
        self.coverage = QCheckBox("Inclure le contrôle de couverture")
        self.coverage.setChecked(True)
        layout.addWidget(self.coverage)
        self.findings = QCheckBox("Inclure le détail des constats")
        self.findings.setChecked(True)
        layout.addWidget(self.findings)
        note = QLabel(
            "Le rapport reprend le client, la mission, les machines, les indicateurs, les "
            "actions et les destructions enregistrés dans le case."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Générer…")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def options(self):
        return dict(
            title=self.title.text().strip(),
            analyst=self.analyst.text().strip(),
            graph=self.graph.isChecked(),
            coverage=self.coverage.isChecked(),
            findings=self.findings.isChecked(),
        )


class CaseCommandsMixin:
    """Two commands the case needs and no document-level mixin owns."""

    def destroy_case(self):
        """Delete the whole case: evidence, analyses, tracking, history, then the folder."""
        from fireblade.ui.case_destruction_dialog import CaseDestructionDialog

        if self.active_investigation is None:
            self.error("Ouvrez le case à supprimer.")
            return
        if not self.can_switch_investigation():
            return
        dialog = CaseDestructionDialog(self)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    def after_case_destroyed(self, case):
        """The folder is gone: the window must not keep pointing at it."""
        if (
            self.active_investigation
            and case
            and self.active_investigation.get("id") == case.get("id")
        ):
            self.clear_investigation_workspace()
            self.active_investigation = None
            self.refresh_investigations()
            self.update_investigation_badge()
            self.statusBar().showMessage("Case détruit : " + str(case.get("name", "")))

    def destroy_evidence(self):
        from fireblade.ui.destruction_dialog import DestructionDialog

        if self.active_investigation is None:
            self.error("Ouvrez le case dont les preuves doivent être détruites.")
            return
        if not self.can_switch_investigation():
            return
        dialog = DestructionDialog(self)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()
        panel = getattr(self, "operations_panel", None)
        if panel is not None:
            panel.refresh()

    def client_report(self):
        if self.active_investigation is None:
            self.error("Ouvrez un case avant de générer son rapport client.")
            return
        case = self.active_investigation
        folder = self.investigation_library.folder(case["id"])
        try:
            workspace = case_workspace.load(folder)
        except (OSError, ValueError) as exc:
            self.error(str(exc))
            return
        default = "Rapport d'investigation — " + (workspace["client"].get("name") or case["name"])
        dialog = ClientReportDialog(self, default, workspace["engagement"].get("lead", ""))
        try:
            if dialog.exec() != QDialog.Accepted:
                return
            options = dialog.options()
        finally:
            dialog.deleteLater()
        if not options["title"]:
            self.error("Le titre du rapport est requis.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer le rapport client",
            "rapport-client.html",
            "Rapport HTML (*.html);;Rapport PDF (*.pdf)",
        )
        if not path:
            return
        panel = getattr(self, "hayabusa_panel", None)
        if panel is not None:
            panel.reload_if_stale()
        findings = list(getattr(panel, "groups", []) or []) if panel else []
        incidents = list(getattr(panel, "incidents", []) or []) if panel else []
        graph_png = None
        graph_panel = getattr(self, "graph_panel", None)
        if options["graph"] and graph_panel is not None:
            graph_panel.reload(reload_workspace=False)
            if graph_panel.canvas.graph.get("nodes"):
                graph_png = base64.b64encode(graph_panel.canvas.render_png()).decode("ascii")
        coverage = None
        if options["coverage"]:
            try:
                self.coverage_panel.ensure_context()
                coverage = self.coverage_panel.report
            except Exception:
                coverage = None
        documents = list(self.documents)
        destruction_records = workspace.get("destruction") or []
        pdf = Path(path).suffix.casefold() == ".pdf"

        def work():
            document = client_report.build(
                title=options["title"],
                case_name=case["name"],
                case_id=case["id"],
                workspace=workspace,
                documents=documents,
                findings=findings if options["findings"] else [],
                incidents=incidents if options["findings"] else [],
                graph_png=graph_png,
                coverage=coverage,
                destruction=destruction_records,
                analyst=options["analyst"],
            )
            document["path"] = client_report.write(path, document, pdf=pdf)
            return document

        def done(document):
            self.statusBar().showMessage(
                f"Rapport client créé : {document['findings']} constat(s), "
                f"{document['open_actions']} action(s) ouverte(s) · {document['path']}"
            )
            if (
                QMessageBox.question(self, "Rapport client", "Rapport enregistré.\n\nL'ouvrir ?")
                == QMessageBox.Yes
            ):
                QDesktopServices.openUrl(QUrl.fromLocalFile(document["path"]))

        self.statusBar().showMessage("Génération du rapport client…")
        self.run(work, done, exclusive=True)
