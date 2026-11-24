"""The rules an analyst may want to change, shown beside the rule itself.

A detection rule is a small text file; the analyst needs to read it, tighten it to their
environment, switch it off for a run, and see what the next analysis would load. The
dialog never edits the delivered pack: saving writes an override in the user folder, and
the next run builds its rules folder from both.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from fireblade.core import hayabusa_rules
from fireblade.core.i18n import translate


class HayabusaRulesDialog(QDialog):
    def __init__(self, pack_rules, parent=None, base=None):
        super().__init__(parent)
        self.pack_rules = Path(pack_rules)
        self.base = base
        self.rows = []
        self.current_name = ""
        self.setWindowTitle(translate("Règles Hayabusa"))
        self.resize(980, 620)
        layout = QVBoxLayout(self)

        intro = QLabel(
            translate(
                "Ces règles sont celles de la détection. Une modification est "
                "enregistrée dans votre dossier de règles et s’applique à la "
                "prochaine analyse ; le pack livré n’est jamais modifié."
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(translate("Chercher un titre, un identifiant ou un niveau…"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        self.only_changed = QPushButton(translate("Modifiées seulement"))
        self.only_changed.setCheckable(True)
        self.only_changed.toggled.connect(self.refresh)
        search_row.addWidget(self.search, 1)
        search_row.addWidget(self.only_changed)
        layout.addLayout(search_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            [
                translate("Règle"),
                translate("Titre"),
                translate("Niveau"),
                translate("Source"),
                translate("Active"),
            ]
        )
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self.show_selected)
        layout.addWidget(self.table, 3)

        self.editor = QPlainTextEdit()
        self.editor.setTabChangesFocus(True)
        self.editor.setPlaceholderText(
            translate("Sélectionnez une règle pour la lire et la modifier.")
        )
        layout.addWidget(self.editor, 2)

        buttons = QHBoxLayout()
        self.save_button = QPushButton(translate("Enregistrer la règle"))
        self.save_button.clicked.connect(self.save_rule)
        self.reset_button = QPushButton(translate("Rétablir celle du pack"))
        self.reset_button.clicked.connect(self.reset_rule)
        self.toggle_button = QPushButton(translate("Désactiver cette règle"))
        self.toggle_button.clicked.connect(self.toggle_rule)
        for button in (self.save_button, self.reset_button, self.toggle_button):
            button.setEnabled(False)
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.button(QDialogButtonBox.Close).setText(translate("Fermer"))
        close.rejected.connect(self.reject)
        layout.addWidget(close)
        self.refresh()

    # -- listing ---------------------------------------------------------------------
    def refresh(self):
        needle = self.search.text().strip().casefold()
        try:
            rows = hayabusa_rules.inventory(self.pack_rules, self.base)
        except Exception as exc:  # noqa: BLE001 - the dialog must stay readable
            self.status.setText(translate("Règles indisponibles : ") + str(exc))
            rows = []
        if self.only_changed.isChecked():
            rows = [row for row in rows if row["source"] == "user" or not row["enabled"]]
        if needle:
            rows = [
                row
                for row in rows
                if needle in (row["name"] + " " + row["title"] + " " + row["level"]).casefold()
            ]
        self.rows = rows
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            values = [
                row["name"],
                row["title"],
                row["level"] or "—",
                translate("utilisateur") if row["source"] == "user" else translate("pack"),
                translate("oui") if row["enabled"] else translate("non"),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if not row["enabled"]:
                    item.setForeground(Qt.gray)
                self.table.setItem(index, column, item)
        self.status.setText(
            translate("{} règle(s) · {} modifiée(s) · {} désactivée(s)").format(
                len(rows),
                sum(1 for row in rows if row["source"] == "user"),
                sum(1 for row in rows if not row["enabled"]),
            )
        )
        self.show_selected()

    def selected_row(self):
        index = self.table.currentRow()
        return self.rows[index] if 0 <= index < len(self.rows) else None

    def show_selected(self):
        row = self.selected_row()
        if row is None:
            for button in (self.save_button, self.reset_button, self.toggle_button):
                button.setEnabled(False)
            return
        self.current_name = row["name"]
        try:
            self.editor.setPlainText(
                hayabusa_rules.read_rule(self.pack_rules, row["name"], self.base)
            )
        except Exception as exc:  # noqa: BLE001
            self.editor.setPlainText("")
            self.status.setText(str(exc))
        self.save_button.setEnabled(True)
        self.reset_button.setEnabled(row["source"] == "user")
        self.toggle_button.setEnabled(True)
        self.toggle_button.setText(
            translate("Désactiver cette règle")
            if row["enabled"]
            else translate("Réactiver cette règle")
        )

    # -- actions ---------------------------------------------------------------------
    def save_rule(self):
        row = self.selected_row()
        if row is None:
            return
        try:
            hayabusa_rules.save_rule(
                self.pack_rules, row["name"], self.editor.toPlainText(), self.base
            )
        except ValueError as exc:
            QMessageBox.warning(self, translate("Règle refusée"), str(exc))
            return
        except OSError as exc:
            QMessageBox.warning(self, translate("Enregistrement impossible"), str(exc))
            return
        self.status.setText(
            translate("Règle enregistrée pour la prochaine analyse : ") + row["name"]
        )
        self.refresh()

    def reset_rule(self):
        row = self.selected_row()
        if row is None:
            return
        hayabusa_rules.reset_rule(row["name"], self.base)
        self.status.setText(translate("La règle du pack est rétablie : ") + row["name"])
        self.refresh()

    def toggle_rule(self):
        row = self.selected_row()
        if row is None:
            return
        hayabusa_rules.set_enabled(row["name"], not row["enabled"], self.base)
        self.status.setText(
            (
                translate("Règle désactivée : ")
                if row["enabled"]
                else translate("Règle réactivée : ")
            )
            + row["name"]
        )
        self.refresh()
