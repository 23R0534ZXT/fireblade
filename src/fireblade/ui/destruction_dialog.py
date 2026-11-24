"""Destroy-evidence dialog: choose the files, the scheme, the witnesses, then sign.

The dialog is deliberately slow to accept. The list shows what will disappear, the
scheme is named, the operator and witness are recorded, the reason is required, and the
word ``DETRUIRE`` has to be typed. The case's own record — ``case.json``,
``workspace.json``, the session and the history — is never listed and is refused if a
crafted path points at it: a certificate cannot exist if its own folder was destroyed.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
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
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
)

from fireblade.core import case_workspace, destruction, destruction_certificate

PROTECTED = ("case.json", "workspace.json", "case.lock", "case.active.lock")
PROTECTED_FOLDERS = ("history", "destruction")


class DestructionJob(QThread):
    progressed = Signal(int, int, str)

    def __init__(self, entries, method, operator, witness, reason):
        super().__init__()
        self.entries, self.method, self.operator = entries, method, operator
        self.witness, self.reason = witness, reason
        self.record = None
        self.error = None

    def run(self):
        try:
            self.record = destruction.destroy(
                self.entries,
                self.method,
                operator=self.operator,
                witness=self.witness,
                reason=self.reason,
                progress=lambda done, total, path: self.progressed.emit(done, total, str(path)),
            )
        except Exception as exc:  # reported to the dialog, never swallowed
            self.error = str(exc)


def evidence_files(folder):
    """Everything in the case that can be destroyed, with the record kept out of it."""
    folder = Path(folder)
    protected = {name.casefold() for name in PROTECTED}
    found = []
    for path in sorted(folder.rglob("*")):
        if path.is_dir() or path.is_symlink() or not path.is_file():
            continue
        parts = [part.casefold() for part in path.relative_to(folder).parts]
        if parts and parts[0] in PROTECTED_FOLDERS:
            continue
        if parts[-1] in protected:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        found.append((path, size))
    found.sort(key=lambda item: (-item[1], str(item[0])))
    return found


def human_size(size):
    for unit in ("o", "Kio", "Mio", "Gio", "Tio"):
        if size < 1024 or unit == "Tio":
            return f"{size:.0f} {unit}" if unit == "o" else f"{size:.1f} {unit}"
        size /= 1024
    return str(size)


class DestructionDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("Détruire des preuves et produire le procès-verbal")
        self.resize(860, 640)
        self.case = getattr(window, "active_investigation", None)
        self.folder = window.investigation_library.folder(self.case["id"]) if self.case else None
        self.attachments = []
        self.job = None
        self._build()
        self.populate()

    def _build(self):
        layout = QVBoxLayout(self)
        warning = QLabel(
            "Cette opération est irréversible. Fireblade écrase les fichiers sélectionnés, "
            "vérifie la dernière passe par relecture, puis les supprime, et produit un "
            "procès-verbal signé avec les empreintes avant/après."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("background:#fff3c4;padding:10px;")
        layout.addWidget(warning)
        top = QHBoxLayout()
        self.method = QComboBox()
        for code, spec in destruction.METHODS.items():
            self.method.addItem(spec["label"], code)
        top.addWidget(QLabel("Méthode :"))
        top.addWidget(self.method)
        top.addStretch()
        self.total = QLabel()
        top.addWidget(self.total)
        layout.addLayout(top)
        form = QFormLayout()
        self.operator = QLineEdit(
            self.window.preferences.analyst_name
            if hasattr(self.window.preferences, "analyst_name")
            else ""
        )
        self.witness = QLineEdit()
        self.reason = QPlainTextEdit()
        self.reason.setMaximumHeight(70)
        self.reason.setPlaceholderText(
            "Fin de mission, restitution du matériel, décision du client…"
        )
        form.addRow("Opérateur :", self.operator)
        form.addRow("Témoin :", self.witness)
        form.addRow("Motif / base légale :", self.reason)
        layout.addLayout(form)
        self.list = QListWidget()
        self.list.itemChanged.connect(self.update_total)
        layout.addWidget(QLabel("Fichiers du case :"))
        layout.addWidget(self.list, 1)
        row = QHBoxLayout()
        all_button = QPushButton("Tout sélectionner")
        all_button.clicked.connect(lambda: self.set_all(True))
        row.addWidget(all_button)
        none_button = QPushButton("Tout désélectionner")
        none_button.clicked.connect(lambda: self.set_all(False))
        row.addWidget(none_button)
        photos = QPushButton("Joindre photos / captures…")
        photos.clicked.connect(self.add_attachments)
        row.addWidget(photos)
        self.photo_label = QLabel("Aucune pièce jointe")
        row.addWidget(self.photo_label, 1)
        layout.addLayout(row)
        confirm = QHBoxLayout()
        self.understood = QCheckBox("Je comprends que cette opération est irréversible.")
        self.understood.toggled.connect(self.check_ready)
        confirm.addWidget(self.understood)
        confirm.addWidget(QLabel("Tapez DETRUIRE :"))
        self.phrase = QLineEdit()
        self.phrase.setMaximumWidth(160)
        self.phrase.textChanged.connect(self.check_ready)
        confirm.addWidget(self.phrase)
        confirm.addStretch()
        layout.addLayout(confirm)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.go = QPushButton("Détruire et produire le PV")
        self.go.setEnabled(False)
        self.go.clicked.connect(self.start)
        buttons.addButton(self.go, QDialogButtonBox.AcceptRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def populate(self):
        self.list.clear()
        if self.folder is None:
            self.status.setText(
                "Aucun case actif : ouvrez le case dont les preuves doivent être détruites."
            )
            return
        files = evidence_files(self.folder)
        if not files:
            self.status.setText("Ce case ne contient aucun fichier pouvant être détruit.")
        for path, size in files:
            item = QListWidgetItem(
                f"{path.relative_to(self.folder).as_posix()}   —   {human_size(size)}"
            )
            item.setData(Qt.UserRole, str(path))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.list.addItem(item)
        self.update_total()

    def set_all(self, checked):
        for index in range(self.list.count()):
            self.list.item(index).setCheckState(Qt.Checked if checked else Qt.Unchecked)

    def selected(self):
        return [
            self.list.item(index).data(Qt.UserRole)
            for index in range(self.list.count())
            if self.list.item(index).checkState() == Qt.Checked
        ]

    def update_total(self, *_):
        size = 0
        for path in self.selected():
            try:
                size += Path(path).stat().st_size
            except OSError:
                continue
        passes = len(destruction.METHODS[self.method.currentData()]["passes"]) + 1
        self.total.setText(
            f"{len(self.selected())} fichier(s) · {human_size(size)} · "
            f"environ {human_size(size * passes)} écrits"
        )
        self.check_ready()

    def check_ready(self, *_):
        ready = (
            self.folder is not None
            and self.selected()
            and self.understood.isChecked()
            and self.phrase.text().strip().upper() == "DETRUIRE"
            and self.operator.text().strip()
            and self.reason.toPlainText().strip()
        )
        self.go.setEnabled(bool(ready))
        if ready:
            self.status.setText(
                "Prêt. Le procès-verbal sera enregistré dans le dossier destruction du case."
            )

    def add_attachments(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Joindre des photos ou des captures", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if not paths:
            return
        self.attachments.extend(paths[: 20 - len(self.attachments)])
        self.photo_label.setText(f"{len(self.attachments)} pièce(s) jointe(s)")

    def start(self):
        if self.folder is None:
            return
        open_paths = {
            str(getattr(document, "path", "")) for document in getattr(self.window, "documents", [])
        }
        blocked = [path for path in self.selected() if str(Path(path)) in open_paths]
        if blocked:
            self.window.error(
                "Fermez les analyses ouvertes avant de détruire leurs fichiers : "
                + ", ".join(Path(path).name for path in blocked)
            )
            return
        answer = QMessageBox.question(
            self,
            "Confirmer la destruction",
            f"{len(self.selected())} fichier(s) vont être écrasés puis supprimés sans possibilité de retour. "
            "Continuer ?",
        )
        if answer != QMessageBox.Yes:
            return
        try:
            entries = destruction.plan(self.selected(), self.folder)
            self.attachments = destruction_certificate.store_attachments(
                self.folder, self.attachments
            )
        except (OSError, ValueError) as exc:
            self.window.error(str(exc))
            return
        self.progress = QProgressDialog("Destruction en cours…", None, 0, 100, self)
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.setCancelButton(None)
        self.job = DestructionJob(
            entries,
            self.method.currentData(),
            self.operator.text(),
            self.witness.text(),
            self.reason.toPlainText(),
        )
        self.job.progressed.connect(self.on_progress)
        self.job.finished.connect(self.finish)
        self.go.setEnabled(False)
        self.job.start()

    def on_progress(self, done, total, path):
        percent = int(done * 100 / total) if total else 0
        self.progress.setValue(min(100, percent))
        self.progress.setLabelText(f"{percent} % — {Path(path).name}")

    def finish(self):
        self.progress.setValue(100)
        self.progress.close()
        if self.job.error:
            self.window.error("Destruction interrompue : " + self.job.error)
            return
        record = self.job.record
        record["attachments"] = self.attachments
        try:
            destruction.store_record(self.folder, record)
            document = destruction_certificate.build(
                record,
                case_name=self.case["name"],
                case_id=self.case["id"],
                client=(case_workspace.load(self.folder).get("client") or {}),
                case_folder=self.folder,
            )
            folder = self.folder / "destruction"
            folder.mkdir(exist_ok=True)
            stamp = record["started"][:19].replace(":", "-")
            html_path = destruction_certificate.write(folder / f"PV-{stamp}.html", document)
            pdf_path = destruction_certificate.write(folder / f"PV-{stamp}.pdf", document, pdf=True)
            self.record_destruction(record)
        except (OSError, ValueError) as exc:
            self.window.error("Fichiers détruits mais procès-verbal incomplet : " + str(exc))
            return
        self.populate()
        self.understood.setChecked(False)
        self.phrase.clear()
        self.status.setText(f"Destruction terminée · {record['status']} · PV : {html_path}")
        if (
            QMessageBox.question(
                self,
                "Procès-verbal produit",
                f"{len(record['files'])} fichier(s) traité(s).\n\nOuvrir le PDF ?",
            )
            == QMessageBox.Yes
        ):
            QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path))

    def record_destruction(self, record):
        entry = dict(
            id=record["id"],
            method=record["method"],
            started=record["started"],
            finished=record["finished"],
            status=record["status"],
            label=record["label"],
            operator=record["operator"],
            witness=record["witness"],
            files=[
                dict(
                    relative=item["relative"],
                    size=item["size"],
                    sha256_before=item["sha256_before"],
                    sha256_after=item.get("sha256_after"),
                    state=item["state"],
                    verified=item["verified"],
                )
                for item in record["files"]
            ],
        )

        def change(data):
            data["destruction"].append(entry)

        try:
            case_workspace.mutate(self.folder, change)
        except (OSError, ValueError) as exc:
            self.window.error(str(exc))
