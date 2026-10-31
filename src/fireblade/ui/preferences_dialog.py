import copy
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QPushButton,
    QColorDialog,
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
        self.palette=dict(preferences.theme_palette)
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
        self.auto_profiles = QCheckBox(
            "Appliquer le profil forensic reconnu à l’import"
        )
        self.auto_profiles.setChecked(preferences.auto_profiles)
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
        colors=QPushButton("Personnaliser les couleurs…");colors.clicked.connect(self.edit_palette);form.addRow(colors)
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
        for widget in (self.headers, self.right, self.multiline, self.auto_profiles):
            form.addRow(widget)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def edit_palette(self):
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QPalette
        values=dict(self.palette);dialog=QDialog(self);dialog.setWindowTitle('Couleurs du thème');form=QFormLayout(dialog)
        for label,key,role in [('Fenêtres','window',QPalette.Window),('Texte','text',QPalette.Text),('Grille et champs','base',QPalette.Base),('Lignes alternées','alternate',QPalette.AlternateBase),('Sélection','highlight',QPalette.Highlight),('Texte sélectionné','selection_text',QPalette.HighlightedText)]:
            button=QPushButton(values.get(key,QApplication.palette().color(role).name()))
            def choose(_=False,key=key,button=button):
                color=QColorDialog.getColor(QColor(button.text()),dialog)
                if color.isValid():values[key]=color.name();button.setText(color.name())
            button.clicked.connect(choose);form.addRow(label,button)
        reset=QPushButton('Rétablir les couleurs du thème')
        def clear():values.clear();dialog.accept()
        reset.clicked.connect(clear);form.addRow(reset)
        box=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);box.accepted.connect(dialog.accept);box.rejected.connect(dialog.reject);form.addRow(box)
        if dialog.exec():self.palette=values
        dialog.deleteLater()

    def accept(self):
        p = self.preferences
        p.theme_palette=dict(self.palette)
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
        p.auto_profiles = self.auto_profiles.isChecked()
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
