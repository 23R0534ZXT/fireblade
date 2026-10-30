"""Small desktop dialogs, independent from the database and worker lifecycle."""
from pathlib import Path
import sys

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget)

from .windows_paths import analyses_directory


class ImportDialog(QDialog):
    """One confirmation for destination and optional CSV decoding settings."""

    def __init__(self, source, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ouvrir un CSV")
        self.setMinimumWidth(520)
        source = Path(source)
        directory = analyses_directory() if sys.platform == "win32" else source.parent
        target = directory / (source.stem + ".timeline")
        number = 2
        while target.exists():
            target = directory / f"{source.stem}-{number}.timeline"
            number += 1
        layout = QVBoxLayout(self)
        filename = QLabel(source.name)
        filename.setToolTip(str(source))
        layout.addWidget(filename)
        form = QFormLayout()
        destination = QHBoxLayout()
        self.target = QLineEdit(str(target))
        destination.addWidget(self.target, 1)
        browse = QPushButton("Parcourir…")
        browse.clicked.connect(self.browse)
        destination.addWidget(browse)
        form.addRow("Enregistrer l’analyse :", destination)
        layout.addLayout(form)
        options = QCheckBox("Options du CSV")
        layout.addWidget(options)
        advanced = QWidget()
        fields = QFormLayout(advanced)
        fields.setContentsMargins(0, 0, 0, 0)
        self.separator = QComboBox()
        for label, value in [("Automatique", None), ("Virgule", ","), ("Point-virgule", ";"), ("Tabulation", "\t"), ("Pipe", "|")]:
            self.separator.addItem(label, value)
        self.encoding = QComboBox()
        self.encoding.addItems(["utf-8", "utf-16", "cp1252", "latin-1"])
        fields.addRow("Séparateur :", self.separator)
        fields.addRow("Encodage :", self.encoding)
        layout.addWidget(advanced)
        advanced.hide()
        options.toggled.connect(advanced.setVisible)
        self.message = QLabel()
        layout.addWidget(self.message)
        buttons = QDialogButtonBox(QDialogButtonBox.Open | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Open).setText("Ouvrir")
        buttons.button(QDialogButtonBox.Cancel).setText("Annuler")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse(self):
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer l’analyse", self.target.text(), "Analyse (*.timeline)")
        if path:
            self.target.setText(path)

    def accept(self):
        if not self.target.text().strip():
            self.message.setText("Choisissez le fichier où enregistrer l’analyse.")
            return
        target = Path(self.target.text()).expanduser()
        if target.is_dir():
            self.message.setText("Choisissez un nom de fichier, pas un dossier.")
            return
        if target.suffix.lower() != ".timeline":
            target = target.with_name(target.name + ".timeline")
        self.target.setText(str(target))
        if target.exists():
            self.message.setText("Ce fichier existe déjà. Choisissez un nouveau nom.")
            return
        self.message.clear()
        super().accept()

    def values(self):
        return (Path(self.target.text()).expanduser(), self.separator.currentData(),
                self.encoding.currentText())
