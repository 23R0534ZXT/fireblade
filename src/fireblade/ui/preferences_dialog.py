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
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel, QTableWidget, QTableWidgetItem, QApplication, QTabWidget,
)


class PreferencesDialog(QDialog):
    def __init__(self, preferences, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Préférences")
        self.preferences = copy.deepcopy(preferences)
        self.palette=dict(preferences.theme_palette)
        root=QVBoxLayout(self)
        self.pages=QTabWidget();root.addWidget(self.pages,1)
        self.page_scrolls=[];forms=[]
        for title in ('Apparence','Grille et copie','Dates','Compatibilité'):
            scroll=QScrollArea();scroll.setWidgetResizable(True)
            content=QWidget();page_form=QFormLayout(content)
            page_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            page_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
            scroll.setWidget(content);self.pages.addTab(scroll,title)
            self.page_scrolls.append(scroll);forms.append(page_form)
        self.scroll=self.page_scrolls[0]
        form,grid,dates,compatibility=forms
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
        from fireblade.core.themes import THEMES
        self.skin=QComboBox()
        self.skin.addItem('Standard / personnalisé','')
        for key,preset in THEMES.items():self.skin.addItem(preset.name,key)
        self.skin.setCurrentIndex(self.skin.findData(preferences.theme_preset))
        form.addRow("Galerie de thèmes",self.skin)
        form.addRow("Mode", self.theme)
        note=QLabel('Thèmes clairs, nuit profonde, nuit éclairée et ambiances Studio / Code. L’aperçu reste local jusqu’à validation ; les couleurs peuvent être personnalisées.')
        note.setWordWrap(True);form.addRow(note)
        self.preview=QWidget();preview_layout=QVBoxLayout(self.preview)
        preview_layout.setContentsMargins(5,5,5,5)
        self.preview_table=QTableWidget(2,2)
        self.preview_table.setHorizontalHeaderLabels(['Événement','Utilisateur'])
        self.preview_table.setItem(0,0,QTableWidgetItem('Ouverture'))
        self.preview_table.setItem(0,1,QTableWidgetItem('alice'))
        self.preview_table.setItem(1,0,QTableWidgetItem('Modification'))
        self.preview_table.setItem(1,1,QTableWidgetItem('bob'))
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview_table.selectRow(0)
        self.preview_table.setFixedHeight(100)
        preview_layout.addWidget(self.preview_table)
        controls=QHBoxLayout();controls.addWidget(QLineEdit('Rechercher un événement'))
        controls.addWidget(QPushButton('Ouvrir'));preview_layout.addLayout(controls)
        form.addRow('Aperçu',self.preview)
        self.skin.currentIndexChanged.connect(self.choose_skin)
        self.theme.currentIndexChanged.connect(self.change_mode)
        self.refresh_preview()
        colors=QPushButton("Personnaliser les couleurs…");colors.clicked.connect(self.edit_palette);form.addRow(colors)
        form.addRow("Police", self.font)
        form.addRow("Taille en points", self.size)
        dates.addRow("Dates reconnues", self.dates)
        grid.addRow("Position des détails", self.details)
        self.pattern = QLineEdit(preferences.custom_date_format)
        dates.addRow("Format de date personnalisé", self.pattern)
        date_hint=QLabel('Ces réglages changent la présentation. Les conversions créent des colonnes séparées ; les valeurs source restent conservées.')
        date_hint.setWordWrap(True);dates.addRow(date_hint)
        self.pins = QPlainTextEdit("\n".join(preferences.first_pinned_columns))
        self.pins.setMaximumHeight(70)
        self.pins.setPlaceholderText("Un nom de colonne par ligne")
        grid.addRow("Épinglage par défaut", self.pins)
        for widget in (self.headers, self.right, self.multiline):grid.addRow(widget)
        compatibility.addRow(self.auto_profiles)
        compatibility_hint=QLabel('Les imports Timeline Explorer et les lecteurs .NET se trouvent dans Fichier → Compatibilité Timeline Explorer. Les profils organisent les colonnes ; ils ne remplacent pas un parser.')
        compatibility_hint.setWordWrap(True);compatibility.addRow(compatibility_hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        screen=QApplication.primaryScreen()
        if screen:
            area=screen.availableGeometry();self.resize(min(620,int(area.width()*.9)),min(780,int(area.height()*.85)))

    def choose_skin(self):
        from fireblade.core.themes import THEMES
        preset=THEMES.get(self.skin.currentData())
        if preset:
            self.palette={}
            self.theme.setCurrentIndex(self.theme.findData(preset.mode))
        self.refresh_preview()

    def change_mode(self):
        from fireblade.core.themes import THEMES
        preset=THEMES.get(self.skin.currentData())
        if preset and preset.mode!=self.theme.currentData():
            self.skin.setCurrentIndex(0)
        self.refresh_preview()

    def refresh_preview(self):
        from fireblade.core.themes import THEMES
        from fireblade.ui.theme import theme_palette
        preset=THEMES.get(self.skin.currentData())
        colors=(preset.palette() if preset and preset.mode==self.theme.currentData() else {})|self.palette
        palette,stylesheet=theme_palette(self.theme.currentData(),colors)
        self.preview.setPalette(palette);self.preview.setAutoFillBackground(True)
        self.preview.setStyleSheet(stylesheet)
        for widget in self.preview.findChildren(QWidget):widget.setPalette(palette)

    def edit_palette(self):
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QPalette
        from fireblade.core.themes import THEMES
        preset=THEMES.get(self.skin.currentData())
        effective=(preset.palette() if preset else {})|self.palette
        values=dict(self.palette);dialog=QDialog(self);dialog.setWindowTitle('Couleurs du thème');form=QFormLayout(dialog)
        for label,key,role in [('Fenêtres','window',QPalette.Window),('Texte','text',QPalette.Text),('Grille et champs','base',QPalette.Base),('Lignes alternées','alternate',QPalette.AlternateBase),('Sélection','highlight',QPalette.Highlight),('Texte sélectionné','selection_text',QPalette.HighlightedText)]:
            button=QPushButton(effective.get(key,QApplication.palette().color(role).name()))
            def choose(_=False,key=key,button=button):
                color=QColorDialog.getColor(QColor(button.text()),dialog)
                if color.isValid():values[key]=color.name();button.setText(color.name())
            button.clicked.connect(choose);form.addRow(label,button)
        reset=QPushButton('Rétablir les couleurs du thème')
        def clear():values.clear();dialog.accept()
        reset.clicked.connect(clear);form.addRow(reset)
        box=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);box.accepted.connect(dialog.accept);box.rejected.connect(dialog.reject);form.addRow(box)
        if dialog.exec():self.palette=values;self.refresh_preview()
        dialog.deleteLater()

    def accept(self):
        p = self.preferences
        p.theme_palette=dict(self.palette)
        p.theme_preset=self.skin.currentData()
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
