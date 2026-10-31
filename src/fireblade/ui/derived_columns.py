"""Small classic dialogs for native derived columns; no source rewriting."""

import copy
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QComboBox,
    QLineEdit,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
)
from fireblade.core.derived import FORMATS
from fireblade.core.windows_zones import WINDOWS_ZONES


class DerivedDialog(QDialog):
    def __init__(self, headers, parent=None, expression=False):
        super().__init__(parent)
        self.setWindowTitle(
            "Colonne calculée" if expression else "Conversion temporelle"
        )
        self.resize(620, 300)
        layout = QFormLayout(self)
        self.name = QLineEdit("Calcul" if expression else "Timestamp UTC")
        layout.addRow("Nouvelle colonne", self.name)
        self.expression_mode = expression
        if expression:
            self.expression = QPlainTextEdit()
            self.expression.setPlaceholderText("Iif([Size] > 1024, 'large', 'small')")
            layout.addRow("Expression", self.expression)
        else:
            self.source = QComboBox()
            self.source.addItems(headers)
            layout.addRow("Colonne source", self.source)
            self.time = QComboBox()
            self.time.addItem("(date et heure dans la même colonne)", None)
            for name in headers:
                self.time.addItem(name, name)
            layout.addRow("Heure séparée", self.time)
            self.format = QComboBox()
            for key, label in FORMATS.items():
                self.format.addItem(label, key)
            layout.addRow("Format source", self.format)
            self.zone = QComboBox()
            self.zone.setEditable(True)
            self.zone.addItems(["UTC", "Europe/Paris", *sorted(WINDOWS_ZONES)])
            layout.addRow("Fuseau des dates sans décalage", self.zone)
            note = QLabel(
                "Les valeurs sources restent intactes. Les valeurs invalides deviennent NULL dans la nouvelle colonne.\nUne date contenant Z ou un décalage explicite conserve son fuseau. Les heures locales suivent les règles DST du fuseau choisi."
            )
            note.setWordWrap(True)
            layout.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def definition(self):
        if self.expression_mode:
            return dict(
                name=self.name.text().strip(),
                operation="expression",
                expression=self.expression.toPlainText(),
            )
        columns = [self.source.currentText()]
        if self.time.currentData():
            columns.append(self.time.currentData())
        return dict(
            name=self.name.text().strip(),
            operation="timestamp",
            columns=columns,
            format=self.format.currentData(),
            timezone=self.zone.currentText().strip(),
        )


def add_columns(window, definitions, finished=None):
    case = window.case
    window.capture_pin_widths()
    view = copy.deepcopy(window.view)
    header=window.tree.header()
    layout=[(header.logicalIndex(i),window.tree.columnWidth(header.logicalIndex(i)),window.tree.isColumnHidden(header.logicalIndex(i))) for i in range(header.count())]

    def done(_):
        window.tree.setModel(None)
        if window.model:
            window.model.deleteLater()
        window.model = None
        window.attach(case, view)
        header=window.tree.header()
        for position,(section,width,hidden) in enumerate(layout):
            header.moveSection(header.visualIndex(section),position)
            window.tree.setColumnWidth(section,width)
            window.tree.setColumnHidden(section,hidden)
            if section in window.tree.pinned:window.tree.frozen.setColumnWidth(section,width)
        if finished:
            finished()
        else:
            window.statusBar().showMessage(
                "Colonnes dérivées ajoutées ; source inchangée"
            )

    window.run(lambda: case.add_derived_columns(definitions), done, exclusive=True)


def edit_derived(window, expression=False):
    if not window.case or not window.can_open_file():
        return
    dialog = DerivedDialog(window.case.headers, window, expression)
    if dialog.exec():
        try:
            from fireblade.core.derived import validate_definition

            definition = validate_definition(dialog.definition())
            add_columns(window, [definition])
        except (ValueError, TypeError) as exc:
            window.error(exc)
    dialog.deleteLater()


def quality(window):
    if not window.case or not window.can_open_file():
        return

    def done(result):
        from PySide6.QtWidgets import QMessageBox

        lines = [
            f"{name} : {bad:,} NULL / {total:,} enregistrements"
            for name, (bad, total) in result.items()
        ]
        QMessageBox.information(
            window,
            "Contrôle des colonnes dérivées",
            "\n".join(lines) if lines else "Aucune colonne dérivée.",
        )

    window.run(window.case.derived_quality, done, exclusive=True)
