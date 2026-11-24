"""Closing a case for good: three or seven passes, then the folder goes.

Deleting a case is not deleting a file. The analyst confirms with the case name, chooses the
passes, says where the certificate goes — outside, since the folder disappears — and the run
overwrites every file the case holds before removing the folders.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from fireblade.core import case_destruction, destruction
from fireblade.core.i18n import translate


class CaseDestructionJob(QThread):
    progressed = Signal(int, int, str)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(
        self, folder, method, operator, witness, reason, certificate_path, case_name="", case_id=""
    ):
        super().__init__()
        self.folder, self.method = folder, method
        self.operator, self.witness, self.reason = operator, witness, reason
        self.certificate_path = certificate_path
        self.case_name, self.case_id = case_name, case_id

    def run(self):
        try:
            record = case_destruction.destroy_case(
                self.folder,
                self.method,
                operator=self.operator,
                witness=self.witness,
                reason=self.reason,
                certificate_path=self.certificate_path,
                case_name=self.case_name,
                case_id=self.case_id,
                progress=lambda text: self.progressed.emit(0, 0, str(text)),
            )
        except Exception as exc:  # noqa: BLE001 - the dialog shows what went wrong
            self.failed.emit(str(exc))
            return
        self.finished_ok.emit(record)


class CaseDestructionDialog(QDialog):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        self.case = getattr(window, "active_investigation", None)
        self.folder = window.investigation_library.folder(self.case["id"]) if self.case else None
        self.job = None
        self.setWindowTitle(translate("Supprimer le case et détruire ses données"))
        self.resize(820, 520)
        self._build()
        self.summarise()

    def _build(self):
        layout = QVBoxLayout(self)
        warning = QLabel(
            translate(
                "Cette opération est irréversible : Fireblade écrase chaque fichier du case "
                "(preuves copiées, analyses, suivi, sessions, historique), vérifie la dernière passe, "
                "les supprime, puis retire le dossier. Le procès-verbal est écrit hors du case."
            )
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("background:#ffd9d9;padding:10px;")
        layout.addWidget(warning)

        form = QFormLayout()
        self.method = QComboBox()
        for code, spec in destruction.METHODS.items():
            self.method.addItem(spec["label"], code)
        form.addRow(translate("Méthode :"), self.method)
        self.operator = QLineEdit(getattr(self.window.preferences, "analyst_name", "") or "")
        self.witness = QLineEdit()
        self.reason = QPlainTextEdit()
        self.reason.setMaximumHeight(60)
        self.reason.setPlaceholderText(
            translate("Clôture d’incident, restitution, décision du client…")
        )
        form.addRow(translate("Opérateur :"), self.operator)
        form.addRow(translate("Témoin :"), self.witness)
        form.addRow(translate("Motif / base légale :"), self.reason)
        layout.addLayout(form)

        destination = QHBoxLayout()
        self.certificate = QLineEdit(self.default_certificate_path())
        browse = QPushButton(translate("Choisir…"))
        browse.clicked.connect(self.choose_certificate)
        destination.addWidget(QLabel(translate("Procès-verbal :")))
        destination.addWidget(self.certificate, 1)
        destination.addWidget(browse)
        layout.addLayout(destination)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        confirm = QHBoxLayout()
        self.understood = QCheckBox(translate("Je comprends que tout le case sera détruit."))
        self.understood.toggled.connect(self.check_ready)
        confirm.addWidget(self.understood)
        confirm.addWidget(QLabel(translate("Tapez le nom du case :")))
        self.phrase = QLineEdit()
        self.phrase.setMaximumWidth(220)
        self.phrase.textChanged.connect(self.check_ready)
        confirm.addWidget(self.phrase)
        confirm.addStretch()
        layout.addLayout(confirm)

        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setVisible(False)
        layout.addWidget(self.bar)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText(translate("Fermer"))
        self.go = QPushButton(translate("Détruire le case et produire le PV"))
        self.go.setEnabled(False)
        self.go.clicked.connect(self.start)
        buttons.addButton(self.go, QDialogButtonBox.AcceptRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # -- facts -----------------------------------------------------------------------
    def case_name(self):
        return str((self.case or {}).get("name") or "")

    def default_certificate_path(self):
        name = (self.case_name() or "case").replace("/", "-").replace("\\", "-")[:60]
        try:
            from fireblade.runtime.windows_paths import documents_directory

            base = Path(documents_directory())
        except Exception:  # noqa: BLE001 - the analyst can still choose the destination
            base = Path.home()
        return str(base / f"PV-destruction-{name}.pdf")

    def summarise(self):
        if not self.folder or not Path(self.folder).is_dir():
            self.summary.setText(translate("Case introuvable : rien à détruire."))
            self.go.setEnabled(False)
            return
        try:
            files, folders, links = case_destruction.collect(self.folder)
        except ValueError as exc:
            self.summary.setText(str(exc))
            self.go.setEnabled(False)
            return
        total = sum(item["size"] for item in files)
        text = translate("{} fichier(s) · {} · {} dossier(s)").format(
            len(files), human_size(total), len(folders)
        )
        if links:
            text += "\n" + translate(
                "{} lien(s) symbolique(s) ne seront pas suivis mais le dossier sera retiré."
            ).format(len(links))
        self.summary.setText(text)

    def choose_certificate(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            translate("Où écrire le procès-verbal ?"),
            self.certificate.text() or "PV-destruction.pdf",
            "PDF (*.pdf);;HTML (*.html)",
        )
        if path:
            if not path.casefold().endswith((".pdf", ".html")):
                path += ".pdf"
            self.certificate.setText(path)

    def check_ready(self, *_):
        ready = (
            self.understood.isChecked()
            and self.phrase.text().strip().casefold() == self.case_name().strip().casefold()
            and bool(self.certificate.text().strip())
            and self.job is None
        )
        self.go.setEnabled(ready)

    # -- run -------------------------------------------------------------------------
    def start(self):
        self.check_ready()
        if not self.go.isEnabled():
            return
        destination = Path(self.certificate.text().strip())
        folder = Path(self.folder)
        if destination == folder or folder in destination.resolve().parents:
            QMessageBox.warning(
                self,
                translate("Procès-verbal mal placé"),
                translate("Le PV doit être écrit hors du case, puisque le case disparaît."),
            )
            return
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, translate("Dossier inaccessible"), str(exc))
            return
        if (
            QMessageBox.question(
                self,
                translate("Confirmer la destruction"),
                translate(
                    "Détruire TOUT le case « {} » avec {} ? Cette action est irréversible."
                ).format(self.case_name(), self.method.currentText()),
            )
            != QMessageBox.Yes
        ):
            return
        # Fireblade must let go of the case before overwriting it: an open analysis
        # keeps the .timeline locked, and a reopened collection keeps its output open.
        try:
            self.window.detach()
        except Exception:  # noqa: BLE001 - a window without an analysis is fine
            pass
        try:
            if getattr(self.window, "collection", None) is not None:
                self.window.collection = None
            release = getattr(self.window, "release_investigation_lease", None)
            if callable(release):
                release()
        except Exception:  # noqa: BLE001
            pass
        self.bar.setVisible(True)
        self.go.setEnabled(False)
        self.job = CaseDestructionJob(
            self.folder,
            self.method.currentData(),
            self.operator.text(),
            self.witness.text(),
            self.reason.toPlainText(),
            destination,
            self.case_name(),
            str((self.case or {}).get("id", "")),
        )
        self.job.progressed.connect(self.on_progress)
        self.job.finished_ok.connect(self.on_finished)
        self.job.failed.connect(self.on_failed)
        self.job.start()

    def on_progress(self, _done, _total, message):
        self.status.setText(message)

    def on_finished(self, record):
        self.bar.setVisible(False)
        self.job = None
        files = len(record.get("files") or [])
        failed = [item for item in record.get("files") or [] if not item.get("deleted")]
        self.status.setText(
            translate("Case détruit : {} fichier(s) · dossier retiré : {} · PV : {}").format(
                files,
                translate("oui") if record.get("folder_removed") else translate("non"),
                record.get("certificate"),
            )
        )
        if failed:
            self.status.setText(
                self.status.text()
                + "\n"
                + translate("{} fichier(s) non supprimé(s) : le dossier est conservé.").format(
                    len(failed)
                )
            )
        self.record = record
        if record.get("folder_removed"):
            self.window.after_case_destroyed(self.case)
        self.check_ready()

    def on_failed(self, message):
        self.bar.setVisible(False)
        self.job = None
        self.status.setText(translate("Destruction interrompue : ") + message)
        QMessageBox.warning(self, translate("Destruction interrompue"), message)
        self.check_ready()


def human_size(size):
    value = float(size)
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if value < 1000 or unit == "To":
            return f"{value:.0f} {unit}" if unit == "o" else f"{value:.1f} {unit}"
        value /= 1000
    return f"{value:.1f} To"
