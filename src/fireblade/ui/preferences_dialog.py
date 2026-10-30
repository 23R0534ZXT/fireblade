import copy
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QDoubleSpinBox,
    QLineEdit,
    QPlainTextEdit,
)


class PreferencesDialog(QDialog):
    def __init__(self, preferences, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Préférences")
        self.preferences = copy.deepcopy(preferences)
        form = QFormLayout(self)
        self.theme = QComboBox()
        self.theme.addItem("Clair", "light")
        self.theme.addItem("Sombre", "dark")
        self.theme.setCurrentIndex(self.theme.findData(preferences.theme))
        self.font = QFontComboBox()
        if preferences.font_family:
            self.font.setCurrentFont(QFont(preferences.font_family))
        self.size = QDoubleSpinBox()
        self.size.setDecimals(2)
        self.size.setRange(8, 32)
        self.size.setValue(preferences.font_size)
        self.headers = QCheckBox("Inclure les en-têtes lors de la copie")
        self.headers.setChecked(preferences.copy_headers)
        self.right = QCheckBox("Copier la cellule au clic droit (Maj : menu)")
        self.right.setChecked(preferences.right_click_copy)
        self.multiline = QCheckBox("Afficher les onglets sur plusieurs rangées")
        self.multiline.setChecked(preferences.multiline_tabs)
        self.dates = QComboBox()
        for label, value in [
            ("Texte source", "source"),
            ("ISO normalisé", "iso"),
            ("ISO avec 7 décimales", "iso7"),
            ("Format personnalisé", "custom"),
        ]:
            self.dates.addItem(label, value)
        self.dates.setCurrentIndex(self.dates.findData(preferences.date_format))
        self.details = QComboBox()
        self.details.addItem("En bas", "bottom")
        self.details.addItem("À droite", "right")
        self.details.addItem("En haut", "top")
        self.details.setCurrentIndex(
            self.details.findData(preferences.details_position)
        )
        form.addRow("Thème", self.theme)
        form.addRow("Police", self.font)
        form.addRow("Taille en points", self.size)
        form.addRow("Dates reconnues", self.dates)
        form.addRow("Détails", self.details)
        self.pattern = QLineEdit(preferences.custom_date_format)
        form.addRow("Format de date personnalisé", self.pattern)
        self.pins = QPlainTextEdit("\n".join(preferences.first_pinned_columns))
        self.pins.setMaximumHeight(70)
        self.pins.setPlaceholderText("Un nom de colonne par ligne")
        form.addRow("Épinglage par défaut", self.pins)
        for widget in (self.headers, self.right, self.multiline):
            form.addRow(widget)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def accept(self):
        p = self.preferences
        p.theme, p.font_family, p.font_size = (
            self.theme.currentData(),
            self.font.currentFont().family(),
            self.size.value(),
        )
        p.copy_headers, p.right_click_copy = (
            self.headers.isChecked(),
            self.right.isChecked(),
        )
        p.multiline_tabs, p.date_format = (
            self.multiline.isChecked(),
            self.dates.currentData(),
        )
        p.details_position = self.details.currentData()
        p.custom_date_format = self.pattern.text()
        p.first_pinned_columns = [
            h.strip() for h in self.pins.toPlainText().splitlines() if h.strip()
        ]
        try:
            p.validate()
        except (ValueError, TypeError) as exc:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Préférences invalides", str(exc))
            return
        super().accept()
