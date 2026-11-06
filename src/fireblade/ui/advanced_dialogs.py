"""Ordinary Qt editors for Boolean conditions and ordered formatting rules."""
import copy
from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog,
    QDoubleSpinBox, QFontComboBox, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox,
    QGridLayout, QSizePolicy, QScrollArea, QTabWidget, QFileDialog, QPushButton, QTableWidget, QVBoxLayout, QWidget, QFormLayout)

from fireblade.core.models import Filter, FilterGroup, FormatRule, SortKey, OPERATORS


class RuleStylePreview(QLabel):
    graphic = None

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.graphic:return
        from PySide6.QtGui import QPainter
        mode,fraction,color=self.graphic
        painter=QPainter(self);painter.setPen(Qt.NoPen);painter.setBrush(color)
        if mode=='bar':painter.drawRect(2,self.height()-5,round((self.width()-4)*fraction),3)
        elif mode=='icon':painter.drawEllipse(self.width()-20,self.height()//2-6,12,12)
        painter.end()


class ExpressionEditor(QWidget):
    """Compose conditions through nested cards and local add/remove actions."""
    def __init__(self, headers, condition=None, parent=None):
        super().__init__(parent)
        self.headers = headers
        self.root = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        hint = QLabel("Choisissez une colonne, une comparaison et une valeur. Ajoutez un sous-groupe pour combiner ET et OU.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setMinimumHeight(230)
        self.canvas = QWidget()
        self.cards = QVBoxLayout(self.canvas)
        self.cards.setContentsMargins(0, 0, 4, 0)
        self.scroll.setWidget(self.canvas)
        layout.addWidget(self.scroll, 1)
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.PlainText)
        self.preview.setContentsMargins(8, 6, 8, 6)
        layout.addWidget(self.preview)
        self.unwrap_single = isinstance(condition, Filter) or (isinstance(condition, FilterGroup) and condition.logic == "not" and len(condition.children) == 1 and isinstance(condition.children[0], Filter))
        initial = FilterGroup("and", [condition]) if self.unwrap_single else condition or FilterGroup()
        self.root = self.add_node(None, initial, notify=False)
        self.cards.addWidget(self.root)
        self.cards.addStretch()
        self.changed()

    def add_node(self, parent, value, notify=True):
        from fireblade.ui.condition_cards import ConditionGroup, ConditionRow
        if isinstance(value, FilterGroup) and value.logic == "not" and len(value.children) == 1 and isinstance(value.children[0], Filter):
            node = ConditionRow(self, value.children[0], parent, inverted=True)
        elif isinstance(value, FilterGroup):
            node = ConditionGroup(self, value, parent)
        else:
            node = ConditionRow(self, value, parent)
        if parent is not None:
            parent.children.append(node)
            parent.refresh_children()
        if notify:
            self.changed()
        return node

    def remove_node(self, node):
        if node.owner is None:
            return
        owner = node.owner
        owner.children.remove(node)
        owner.body.removeWidget(node)
        node.hide()
        node.deleteLater()
        owner.refresh_children()
        self.changed()

    def changed(self, *_):
        if self.root is None:
            return
        from fireblade.ui.condition_cards import ConditionGroup
        def update(node):
            if isinstance(node, ConditionGroup):
                node.refresh_children()
                for child in node.children:
                    update(child)
        update(self.root)
        def describe(value):
            from fireblade.core.i18n import translate
            if isinstance(value, Filter):
                label = translate(dict((code, label) for label, code in OPERATORS).get(value.operator, value.operator)).lower()
                column = self.headers[value.column] if 0 <= value.column < len(self.headers) else translate("Colonne")
                return f"{column} {label}" + (f" « {value.value} »" if value.value and value.operator not in ("empty", "not_empty") else "")
            if not value.children:
                return translate("toutes les lignes") if value.logic == "and" else translate("aucune ligne")
            if value.logic == "not":
                return translate("NON (") + describe(value.children[0]) + ")"
            return "(" + translate(" ET " if value.logic == "and" else " OU ").join(describe(child) for child in value.children) + ")"
        try:
            text = describe(self.value())
            self.preview.setText("Lecture du filtre : " + (text[:497] + "…" if len(text) > 500 else text))
        except ValueError as exc:
            self.preview.setText(str(exc))

    def value(self):
        result = self.root.value()
        if self.unwrap_single and result.logic == "and" and len(result.children) == 1:
            return result.children[0]
        return result


class FilterDialog(QDialog):
    def __init__(self, headers, expression, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Éditeur de filtres · ET / OU / NON")
        area=self.screen().availableGeometry()
        self.resize(min(980,max(360,area.width()-40)),min(720,max(360,area.height()-70)))
        layout = QVBoxLayout(self)
        self.editor = ExpressionEditor(headers, expression)
        layout.addWidget(self.editor)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Appliquer les filtres")
        buttons.button(QDialogButtonBox.Cancel).setText("Annuler")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        try:
            self.expression = self.editor.value()
        except ValueError as exc:
            QMessageBox.warning(self, "Condition invalide", str(exc))
            return
        super().accept()


class SortDialog(QDialog):
    def __init__(self, headers, keys, parent=None):
        super().__init__(parent)
        self.headers = headers
        self.setWindowTitle("Tri sur plusieurs colonnes · priorité de haut en bas")
        self.resize(620, 360)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Colonne", "Type", "Ordre"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        row = QHBoxLayout()
        for label, callback in [("Ajouter", lambda: self.add()), ("Retirer", self.remove), ("Monter", lambda: self.move(-1)), ("Descendre", lambda: self.move(1))]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        self.message = QLabel()
        layout.addWidget(self.message)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        for key in keys:
            self.add(key)

    def add(self, key=None):
        if self.table.rowCount() >= 16:
            self.message.setText("16 colonnes de tri au maximum")
            return
        key = key or SortKey(0)
        index = self.table.rowCount()
        self.table.insertRow(index)
        column, kind, order = QComboBox(), QComboBox(), QComboBox()
        column.addItems(self.headers)
        column.setCurrentIndex(key.column)
        for label, value in [("Texte", "text"), ("Nombre", "number"), ("Date ISO", "timestamp")]:
            kind.addItem(label, value)
        kind.setCurrentIndex(kind.findData(key.kind))
        order.addItems(["Croissant", "Décroissant"])
        order.setCurrentIndex(int(key.descending))
        for c, widget in enumerate((column, kind, order)):
            self.table.setCellWidget(index, c, widget)
        self.table.setCurrentCell(index, 0)

    def remove(self):
        if self.table.currentRow() >= 0:
            self.table.removeRow(self.table.currentRow())

    def values(self):
        return [SortKey(self.table.cellWidget(i, 0).currentIndex(), self.table.cellWidget(i, 1).currentData(),
                        bool(self.table.cellWidget(i, 2).currentIndex())) for i in range(self.table.rowCount())]

    def move(self, delta):
        row = self.table.currentRow()
        other = row + delta
        if row < 0 or not 0 <= other < self.table.rowCount():
            return
        keys = self.values()
        keys[row], keys[other] = keys[other], keys[row]
        self.table.setRowCount(0)
        for key in keys:
            self.add(key)
        self.table.setCurrentCell(other, 0)

    def accept(self):
        self.keys = self.values()
        if len({key.column for key in self.keys}) != len(self.keys):
            self.message.setText("Chaque colonne ne doit apparaître qu’une seule fois")
            return
        super().accept()


class RulesDialog(QDialog):
    def __init__(self, headers, rules, parent=None, functions=None):
        super().__init__(parent)
        self.headers, self.rules = headers, copy.deepcopy(rules)
        self.functions=functions if functions is not None else getattr(getattr(parent,"case",None),"expression_functions",{})
        self.setWindowTitle("Règles de coloration · première règle correspondante prioritaire")
        area=self.screen().availableGeometry()
        self.resize(min(850,max(360,area.width()-30)),min(540,max(381,area.height()-50)))
        self.current = -1
        layout = QVBoxLayout(self)
        self.listing = QListWidget()
        self.listing.setMaximumHeight(80)
        layout.addWidget(self.listing)
        row = QHBoxLayout()
        for label, callback in [("Ajouter", self.add), ("Supprimer", self.remove), ("Monter", lambda: self.move(-1)), ("Descendre", lambda: self.move(1))]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        self.rule_steps=QTabWidget()
        self.condition_page=QWidget();self.condition_layout=QVBoxLayout(self.condition_page)
        self.target_page=QWidget();target_layout=QFormLayout(self.target_page)
        target_layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.appearance_page=QWidget();appearance_layout=QVBoxLayout(self.appearance_page)
        self.rule_steps.addTab(self.condition_page,'1. Quand ?')
        self.rule_steps.addTab(self.target_page,'2. Appliquer à')
        self.rule_steps.addTab(self.appearance_page,'3. Apparence')
        layout.addWidget(self.rule_steps,1)
        self.format_tabs=QTabWidget()
        appearance=QWidget();appearance.setLayout(QVBoxLayout())
        graphic_content=QWidget();graphic_content.setLayout(QVBoxLayout())
        graphic_scroll=QScrollArea();graphic_scroll.setWidgetResizable(True);graphic_scroll.setWidget(graphic_content)
        appearance_scroll=QScrollArea();appearance_scroll.setWidgetResizable(True);appearance_scroll.setWidget(appearance)
        self.format_tabs.addTab(appearance_scroll,'Apparence');self.format_tabs.addTab(graphic_scroll,'Graphique')
        appearance_layout.addWidget(self.format_tabs,1)
        controls = QHBoxLayout()
        self.enabled = QCheckBox("Active")
        target_layout.addRow(self.enabled)
        self.target = QComboBox()
        self.target.addItem("Toute la ligne", None)
        for i, header in enumerate(headers):
            self.target.addItem(header, i)
        target_layout.addRow('Colonne cible',self.target)
        self.background = QPushButton("Fond")
        self.foreground = QPushButton("Texte")
        self.background.clicked.connect(lambda: self.pick_color(self.background))
        self.foreground.clicked.connect(lambda: self.pick_color(self.foreground))
        controls.addWidget(self.background)
        controls.addWidget(self.foreground)
        self.bold = QCheckBox("Gras")
        controls.addWidget(self.bold)
        self.italic, self.underline, self.strikeout = QCheckBox('Italique'), QCheckBox('Souligné'), QCheckBox('Barré')
        for widget in (self.italic, self.underline, self.strikeout):
            controls.addWidget(widget)
        appearance.layout().addLayout(controls)
        visual_row = QHBoxLayout()
        self.visual = QComboBox()
        for label, code in [('Couleurs / texte', 'none'), ('Barre de données', 'bar'), ('Dégradé à 2 couleurs', 'scale'), ('Dégradé à 3 couleurs','scale3'), ('Icônes', 'icon')]:self.visual.addItem(label,code)
        self.visual.setToolTip('Les bornes et percentiles portent sur tous les résultats filtrés, avec cache entre les pages.')
        visual_row.addWidget(self.visual)
        self.value_column=QComboBox();self.value_column.addItem('Valeurs du champ cible',None)
        for i,h in enumerate(headers):self.value_column.addItem(h,i)
        visual_row.addWidget(self.value_column);graphic_content.layout().addLayout(visual_row)
        self.minimum,self.maximum=QLineEdit('0'),QLineEdit('100')
        self.bound_mode,self.high_mode=QComboBox(),QComboBox()
        for combo in (self.bound_mode,self.high_mode):
            for label,code in [('Valeur fixe','fixed'),('Automatique','auto'),('Pourcent de la plage','percent'),('Percentile exact','percentile')]:combo.addItem(label,code)
        bounds=QHBoxLayout()
        for widget in (QLabel('Minimum'),self.bound_mode,self.minimum,QLabel('Maximum'),self.high_mode,self.maximum):bounds.addWidget(widget)
        graphic_content.layout().addLayout(bounds)
        middle=QHBoxLayout();self.middle_color=QPushButton('Couleur médiane');self.middle_color.clicked.connect(lambda:self.pick_color(self.middle_color))
        self.middle_value=QLineEdit('50');self.middle_mode=QComboBox()
        for label,code in [('Valeur fixe','fixed'),('Pourcent de la plage','percent'),('Percentile exact','percentile')]:self.middle_mode.addItem(label,code)
        for widget in (self.middle_color,self.middle_mode,self.middle_value):middle.addWidget(widget)
        graphic_content.layout().addLayout(middle)
        fonts=QHBoxLayout();self.font_family=QFontComboBox();self.font_size=QDoubleSpinBox()
        self.font_size.setRange(0,96);self.font_size.setSpecialValueText('Taille héritée');self.font_size.setDecimals(2)
        self.custom_font=QCheckBox('Police propre à cette règle')
        fonts.addWidget(self.custom_font);fonts.addWidget(self.font_family);fonts.addWidget(self.font_size)
        appearance.layout().addLayout(fonts)
        flags=QHBoxLayout();self.use_background=QCheckBox('Fond actif');self.use_foreground=QCheckBox('Texte actif');self.use_font=QCheckBox('Police active');self.stop_if_true=QCheckBox('Arrêter après cette règle')
        for widget in (self.use_background,self.use_foreground,self.use_font):flags.addWidget(widget)
        target_layout.addRow(self.stop_if_true)
        scope_hint=QLabel('Toute la ligne colore chaque cellule. Une colonne cible limite le style à ce champ. Les règles sont examinées dans l’ordre de la liste.')
        scope_hint.setWordWrap(True);target_layout.addRow(scope_hint)
        appearance.layout().addLayout(flags)
        statistics=QHBoxLayout();self.statistic=QComboBox()
        for label,code in [('Conditions seulement',''),('Valeurs les plus élevées','top'),('Valeurs les plus basses','bottom'),('Au-dessus de la moyenne','above_avg'),('Sous la moyenne','below_avg'),('Moyenne ou plus','above_eq_avg'),('Moyenne ou moins','below_eq_avg'),('Valeurs uniques','unique'),('Doublons','duplicate')]:self.statistic.addItem(label,code)
        self.stat_rank=QLineEdit('10');self.stat_rank.setMaximumWidth(80);self.stat_percent=QCheckBox('Pourcent')
        self.stat_column=QComboBox();self.stat_column.addItem('Valeurs du champ cible',None)
        for i,h in enumerate(headers):self.stat_column.addItem(h,i)
        self.stat_column.currentIndexChanged.connect(self.value_column.setCurrentIndex);self.value_column.currentIndexChanged.connect(self.stat_column.setCurrentIndex)
        for widget in (self.statistic,self.stat_column,self.stat_rank,self.stat_percent):statistics.addWidget(widget)
        appearance.layout().addLayout(statistics)
        matching=QHBoxLayout();self.stat_ignore_case=QCheckBox('Doublons sans distinction de casse');self.stat_include_null=QCheckBox('Inclure les valeurs vides')
        matching.addWidget(self.stat_ignore_case);matching.addWidget(self.stat_include_null);appearance.layout().addLayout(matching)
        self.all_source_rows=QCheckBox('Statistiques et bornes sur toute la source')
        self.all_source_rows.setToolTip('Ignorer les filtres actifs pour calculer les statistiques, minimums, maximums et percentiles.')
        self.all_source_rows.setSizePolicy(QSizePolicy.Maximum,QSizePolicy.Fixed);appearance.layout().addWidget(self.all_source_rows)
        dates=QHBoxLayout();self.relative_date=QComboBox()
        from fireblade.core.date_ranges import RANGES
        for name in RANGES:self.relative_date.addItem(name,name)
        add_date=QPushButton('Ajouter une condition de date relative')
        add_date.setToolTip('UTC ; semaines du lundi au dimanche. Utilise le champ de valeurs ou la cible sélectionnée.')
        def date_condition():
            col=self.value_column.currentData()
            if col is None:col=self.target.currentData()
            if col is None:self.message.setText('Choisir un champ de valeurs ou une colonne cible');return
            name=self.headers[col].replace(']',']]')
            self.editor.add_node(self.editor.root,Filter(col,'expression',f"InDateRange([{name}], '{self.relative_date.currentData()}')"))
        add_date.clicked.connect(date_condition);dates.addWidget(self.relative_date);dates.addWidget(add_date);appearance.layout().addLayout(dates)
        self.show_values=QCheckBox('Afficher les valeurs');graphic_content.layout().addWidget(self.show_values)
        bar=QHBoxLayout();self.zero_based=QCheckBox('Bornes automatiques incluant zéro');self.draw_axis=QCheckBox('Tracer l’axe zéro')
        self.negative_color=QPushButton('Couleur négative');self.axis_color=QPushButton('Couleur de l’axe')
        self.negative_color.clicked.connect(lambda:self.pick_color(self.negative_color));self.axis_color.clicked.connect(lambda:self.pick_color(self.axis_color))
        for widget in (self.zero_based,self.draw_axis,self.negative_color,self.axis_color):bar.addWidget(widget)
        graphic_content.layout().addLayout(bar)
        self.icons_widget=QWidget();icons=QGridLayout(self.icons_widget)
        self.icon_levels=QComboBox()
        for count in (3,4,5):self.icon_levels.addItem(f'{count} niveaux',count)
        self.icon_set=QComboBox()
        for label,code in [('Ronds','circles'),('Flèches','arrows'),('Signes','signs'),('Triangles','triangles'),('Carrés','squares'),('Losanges','diamonds'),('Étoiles','stars'),('Classements','ratings'),('Drapeaux','flags')]:self.icon_set.addItem(label,code)
        self.icon_threshold_mode=QComboBox()
        for label,code in [('Seuils en pourcent','percent'),('Seuils numériques','number'),('Seuils en percentiles','percentile')]:self.icon_threshold_mode.addItem(label,code)
        icons.addWidget(self.icon_levels,0,0);icons.addWidget(self.icon_set,0,1);icons.addWidget(self.icon_threshold_mode,0,2,1,2)
        self.icon_colors=[];self.icon_images=[];self.icon_thresholds=[];self.icon_comparisons=[];self.icon_threshold_modes=[]
        for i in range(5):
            color=QPushButton(f'Couleur {i+1}');image=QPushButton(f'Image {i+1}')
            color.clicked.connect(lambda _=False,b=color:self.pick_color(b));image.clicked.connect(lambda _=False,b=image:self.pick_icon(b))
            icons.addWidget(color,1,i);icons.addWidget(image,2,i);self.icon_colors.append(color);self.icon_images.append(image)
            if i<4:
                threshold=QLineEdit();threshold.setPlaceholderText(f'Seuil {i+1}')
                comparison=QComboBox();comparison.addItem('≥','>=');comparison.addItem('>','>')
                pair=QWidget();pair.setLayout(QHBoxLayout());pair.layout().setContentsMargins(0,0,0,0);pair.layout().addWidget(comparison);pair.layout().addWidget(threshold)
                unit=QComboBox()
                for label,code in [('Type commun',''),('Valeur','number'),('Pourcent','percent'),('Percentile','percentile')]:unit.addItem(label,code)
                pair.layout().addWidget(unit);self.icon_threshold_modes.append(unit)
                icons.addWidget(pair,3,i);self.icon_thresholds.append(threshold);self.icon_comparisons.append(comparison)
        floor=QHBoxLayout();self.icon_floor=QLineEdit();self.icon_floor.setPlaceholderText('Plancher facultatif')
        self.icon_floor_mode=QComboBox()
        for label,code in [('Valeur','number'),('Pourcent','percent'),('Percentile','percentile')]:self.icon_floor_mode.addItem(label,code)
        self.icon_floor_comparison=QComboBox();self.icon_floor_comparison.addItem('≥','>=');self.icon_floor_comparison.addItem('>','>')
        for widget in (self.icon_floor,self.icon_floor_mode,self.icon_floor_comparison):floor.addWidget(widget)
        icons.addLayout(floor,5,0,1,5)
        clear=QPushButton('Effacer images');clear.clicked.connect(lambda:[b.setProperty('image','') for b in self.icon_images]);icons.addWidget(clear,4,0,1,2)
        graphic_content.layout().addWidget(self.icons_widget)
        def update_icons():
            count=self.icon_levels.currentData()
            self.icons_widget.setVisible(self.visual.currentData()=='icon')
            for i in range(5):
                self.icon_colors[i].setVisible(i<count);self.icon_images[i].setVisible(i<count)
                if i<4:
                    self.icon_thresholds[i].parentWidget().setVisible(i<count-1)
        self.visual.currentIndexChanged.connect(update_icons);self.icon_levels.currentIndexChanged.connect(update_icons)
        self._update_icons=update_icons
        self.advanced_button=QPushButton('Réglages avancés : statistiques et police')
        self.advanced_button.setCheckable(True)
        self.advanced_options=QWidget();advanced=QVBoxLayout(self.advanced_options)
        advanced.setContentsMargins(0,0,0,0)
        for old_layout in (fonts,flags,statistics,matching,dates):
            appearance.layout().removeItem(old_layout);advanced.addLayout(old_layout)
        appearance.layout().removeWidget(self.all_source_rows);advanced.addWidget(self.all_source_rows)
        appearance.layout().addWidget(self.advanced_button);appearance.layout().addWidget(self.advanced_options)
        self.advanced_options.hide();self.advanced_button.toggled.connect(self.advanced_options.setVisible)
        appearance.layout().addStretch()
        self.sample_value=QLineEdit('42');self.sample_value.setPlaceholderText('Valeur d’exemple')
        self.style_preview=RuleStylePreview();self.style_preview.setTextFormat(Qt.PlainText)
        self.style_preview.setMinimumHeight(36);self.style_preview.setAlignment(Qt.AlignCenter)
        preview_row=QHBoxLayout();preview_row.addWidget(QLabel('Aperçu du style :'));preview_row.addWidget(self.sample_value);preview_row.addWidget(self.style_preview,1)
        appearance_layout.addLayout(preview_row)
        preview_hint=QLabel('Exemple de style uniquement ; la condition et les statistiques de la source ne sont pas évaluées ici.')
        preview_hint.setWordWrap(True);appearance_layout.addWidget(preview_hint)
        for widget in (self.bold,self.italic,self.underline,self.strikeout,self.use_background,self.use_foreground,self.use_font):widget.toggled.connect(self.update_preview)
        for widget in (self.sample_value,self.minimum,self.maximum):widget.textChanged.connect(self.update_preview)
        self.visual.currentIndexChanged.connect(self.update_preview)
        self.font_family.currentFontChanged.connect(self.update_preview)
        self.font_size.valueChanged.connect(self.update_preview)
        self.custom_font.toggled.connect(self.update_preview)
        self.editor = ExpressionEditor(headers)
        self.condition_layout.addWidget(self.editor)
        self.message = QLabel()
        layout.addWidget(self.message)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.listing.currentRowChanged.connect(self.select)
        self.refresh(0 if self.rules else -1)

    def pick_icon(self,button):
        path,_=QFileDialog.getOpenFileName(self,'Choisir une icône','','Images (*.png *.jpg *.jpeg *.bmp)')
        if not path:return
        from PySide6.QtGui import QImageReader
        from PySide6.QtCore import QBuffer,QIODevice,QSize
        import base64
        reader=QImageReader(path);size=reader.size()
        if not size.isValid() or size.width()*size.height()>16000000:
            self.message.setText('Image invalide ou trop grande (16 mégapixels maximum)');return
        reader.setScaledSize(QSize(32,32));image=reader.read()
        if image.isNull():self.message.setText(reader.errorString());return
        buffer=QBuffer();buffer.open(QIODevice.WriteOnly);image.save(buffer,'PNG')
        button.setProperty('image',base64.b64encode(bytes(buffer.data())).decode('ascii'))
        button.setToolTip('Image intégrée dans la règle, sans dépendance au fichier original')

    def pick_color(self, button):
        color = QColorDialog.getColor(QColor(button.property("color") or "#ffffff"), self, options=QColorDialog.ShowAlphaChannel)
        if color.isValid():
            self.set_color(button, color.name(QColor.HexArgb) if color.alpha()!=255 else color.name())
            self.update_preview()

    def update_preview(self, *_):
        if not hasattr(self,'style_preview'):return
        from PySide6.QtGui import QFont, QPalette
        palette=self.palette()
        background=QColor(self.background.property('color') or '#fce2e2')
        foreground=QColor(self.foreground.property('color') or '#202020')
        if self.use_background.isChecked():palette.setColor(QPalette.Window,background)
        if self.use_foreground.isChecked():palette.setColor(QPalette.WindowText,foreground)
        self.style_preview.setPalette(palette);self.style_preview.setAutoFillBackground(True)
        font=QFont(self.font())
        if self.use_font.isChecked():
            if self.custom_font.isChecked():font.setFamily(self.font_family.currentFont().family())
            if self.font_size.value():font.setPointSizeF(self.font_size.value())
            font.setBold(self.bold.isChecked());font.setItalic(self.italic.isChecked())
            font.setUnderline(self.underline.isChecked());font.setStrikeOut(self.strikeout.isChecked())
        self.style_preview.setFont(font)
        self.style_preview.setText(self.sample_value.text())
        from fireblade.ui.visual_rules import visual_value, contrast_color
        self.style_preview.graphic=None
        visual=self.visual.currentData()
        try:
            rule=FormatRule(visual=visual,minimum=self.minimum.text(),maximum=self.maximum.text(),
                background=background.name(),foreground=foreground.name(),middle_color=self.middle_color.property('color') or '#ffffbf',
                middle_value=self.middle_value.text(),middle_mode=self.middle_mode.currentData())
            if visual!='none':self.style_preview.graphic=visual_value(rule,self.sample_value.text())
            if visual in ('scale','scale3') and self.style_preview.graphic:
                color=self.style_preview.graphic[2]
                palette.setColor(QPalette.Window,color);palette.setColor(QPalette.WindowText,contrast_color(color))
                self.style_preview.setPalette(palette)
        except (ValueError,ArithmeticError):pass
        self.style_preview.update()

    @staticmethod
    def set_color(button, color):
        button.setProperty("color", color)
        button.setStyleSheet(f"border-bottom: 4px solid {color};")

    def store(self):
        if self.current >= 0:
            count=self.icon_levels.currentData()
            thresholds=[b.text().strip() for b in self.icon_thresholds[:count-1]]
            if not any(thresholds):thresholds=[]
            self.rules[self.current] = replace(self.rules[self.current],condition=self.editor.value(),background=self.background.property('color'),
                foreground=self.foreground.property('color'),bold=self.bold.isChecked(),target=self.target.currentData(),enabled=self.enabled.isChecked(),visual=self.visual.currentData(),
                minimum=self.minimum.text(),maximum=self.maximum.text(),italic=self.italic.isChecked(),underline=self.underline.isChecked(),strikeout=self.strikeout.isChecked(),
                bound_mode=self.bound_mode.currentData(),maximum_mode=(self.high_mode.currentData() if self.rules[self.current].maximum_mode or self.high_mode.currentData()!=self.bound_mode.currentData() else ""),font_family=self.font_family.currentText() if self.custom_font.isChecked() else '',font_size=self.font_size.value(),
                all_source_rows=self.all_source_rows.isChecked(),statistic=self.statistic.currentData(),stat_rank=self.stat_rank.text(),stat_percent=self.stat_percent.isChecked(),stat_ignore_case=self.stat_ignore_case.isChecked(),stat_include_null=self.stat_include_null.isChecked(),
                zero_based=self.zero_based.isChecked(),draw_axis=self.draw_axis.isChecked(),negative_color=self.negative_color.property("color"),axis_color=self.axis_color.property("color"),
                stop_if_true=self.stop_if_true.isChecked(),use_background=self.use_background.isChecked(),use_foreground=self.use_foreground.isChecked(),use_font=self.use_font.isChecked(),show_values=self.show_values.isChecked(),
                value_column=self.value_column.currentData(),middle_color=self.middle_color.property("color"),middle_value=self.middle_value.text(),middle_mode=self.middle_mode.currentData(),
                icon_set=self.icon_set.currentData(),icon_colors=[b.property('color') for b in self.icon_colors[:count]],icon_images=[b.property('image') or '' for b in self.icon_images[:count]],
                icon_threshold_mode=self.icon_threshold_mode.currentData(),icon_thresholds=thresholds,
                icon_threshold_modes=([c.currentData() or self.icon_threshold_mode.currentData() for c in self.icon_threshold_modes[:count-1]] if thresholds and any(c.currentData() for c in self.icon_threshold_modes[:count-1]) else []),
                icon_comparisons=([c.currentData() for c in self.icon_comparisons[:count-1]] if self.rules[self.current].icon_comparisons or any(c.currentData()!=">=" for c in self.icon_comparisons[:count-1]) else []),
                icon_floor=self.icon_floor.text(),icon_floor_mode=self.icon_floor_mode.currentData(),icon_floor_comparison=self.icon_floor_comparison.currentData())


    def refresh(self, selected):
        self.listing.blockSignals(True)
        self.listing.clear()
        for i, rule in enumerate(self.rules):
            self.listing.addItem(f"{i + 1}. {'Active' if rule.enabled else 'Inactive'} · {self.headers[rule.target] if rule.target is not None else 'Toute la ligne'}")
        self.listing.setCurrentRow(selected)
        self.listing.blockSignals(False)
        self.current = -1
        self.select(selected)

    def select(self, index):
        try:
            self.store()
        except ValueError as exc:
            self.message.setText(str(exc))
            self.listing.blockSignals(True)
            self.listing.setCurrentRow(self.current)
            self.listing.blockSignals(False)
            return
        self.current = index
        rule = self.rules[index] if index >= 0 else FormatRule()
        self.statistic.setCurrentIndex(self.statistic.findData(rule.statistic));self.stat_rank.setText(rule.stat_rank)
        self.enabled.setChecked(rule.enabled)
        for name in ("use_background","use_foreground","use_font","stop_if_true","show_values","zero_based","draw_axis","stat_percent","stat_ignore_case","stat_include_null","all_source_rows"):getattr(self,name).setChecked(getattr(rule,name))
        self.set_color(self.negative_color,rule.negative_color);self.set_color(self.axis_color,rule.axis_color)
        self.target.setCurrentIndex(self.target.findData(rule.target))
        self.bold.setChecked(rule.bold)
        self.italic.setChecked(rule.italic)
        self.underline.setChecked(rule.underline)
        self.strikeout.setChecked(rule.strikeout)
        self.visual.setCurrentIndex(self.visual.findData(rule.visual))
        self.value_column.setCurrentIndex(self.value_column.findData(rule.value_column))
        self.set_color(self.middle_color,rule.middle_color);self.middle_value.setText(rule.middle_value);self.middle_mode.setCurrentIndex(self.middle_mode.findData(rule.middle_mode))
        self.bound_mode.setCurrentIndex(self.bound_mode.findData(rule.bound_mode))
        self.high_mode.setCurrentIndex(self.high_mode.findData(rule.maximum_mode or rule.bound_mode))
        self.custom_font.setChecked(bool(rule.font_family))
        if rule.font_family:
            from PySide6.QtGui import QFont
            self.font_family.setEditText(rule.font_family)
        self.font_size.setValue(rule.font_size)
        self.icon_set.setCurrentIndex(self.icon_set.findData(rule.icon_set))
        self.icon_levels.setCurrentIndex(self.icon_levels.findData(len(rule.icon_colors)))
        self.icon_threshold_mode.setCurrentIndex(self.icon_threshold_mode.findData(rule.icon_threshold_mode))
        defaults=['#c62828','#f57c00','#c58b00','#8dbb38','#218739']
        for i,button in enumerate(self.icon_colors):self.set_color(button,rule.icon_colors[i] if i<len(rule.icon_colors) else defaults[i])
        for i,button in enumerate(self.icon_images):button.setProperty('image',rule.icon_images[i] if i<len(rule.icon_images) else '')
        for i,combo in enumerate(self.icon_threshold_modes):combo.setCurrentIndex(combo.findData(rule.icon_threshold_modes[i] if i<len(rule.icon_threshold_modes) else ''))
        for i,field in enumerate(self.icon_thresholds):field.setText(rule.icon_thresholds[i] if i<len(rule.icon_thresholds) else '')
        for i,combo in enumerate(self.icon_comparisons):combo.setCurrentIndex(combo.findData(rule.icon_comparisons[i] if i<len(rule.icon_comparisons) else '>='))
        self.icon_floor.setText(rule.icon_floor);self.icon_floor_mode.setCurrentIndex(self.icon_floor_mode.findData(rule.icon_floor_mode));self.icon_floor_comparison.setCurrentIndex(self.icon_floor_comparison.findData(rule.icon_floor_comparison))
        self._update_icons()
        self.minimum.setText(rule.minimum)
        self.maximum.setText(rule.maximum)
        self.set_color(self.background, rule.background)
        self.set_color(self.foreground, rule.foreground)
        old = self.editor
        # A dialog's nested event loop can defer deleteLater() until it closes.
        # Retire the old controls immediately so they cannot cover or intercept
        # clicks intended for the replacement editor.
        old.hide()
        old.setEnabled(False)
        self.editor = ExpressionEditor(self.headers, rule.condition)
        self.condition_layout.replaceWidget(old, self.editor)
        old.deleteLater()
        for widget in (self.all_source_rows,self.editor, self.enabled, self.target, self.background, self.foreground, self.bold, self.visual, self.minimum, self.maximum, self.italic, self.underline, self.strikeout, self.bound_mode, self.custom_font, self.font_family, self.font_size,self.high_mode,self.value_column,self.middle_color,self.middle_mode,self.middle_value,self.stop_if_true,self.use_background,self.use_foreground,self.use_font,self.show_values,self.zero_based,self.draw_axis,self.negative_color,self.axis_color,self.statistic,self.stat_rank,self.stat_column,self.stat_percent,self.stat_ignore_case,self.stat_include_null):
            widget.setEnabled(index >= 0)
        for widget in [self.icon_set,self.icon_levels,self.icon_threshold_mode,*self.icon_thresholds,*self.icon_threshold_modes,*self.icon_colors,*self.icon_images]:widget.setEnabled(index>=0)
        self.message.clear()
        self.advanced_button.setChecked(bool(rule.statistic or rule.all_source_rows or rule.font_family))
        self.update_preview()

    def add(self):
        try:
            self.store()
            if len(self.rules) >= 32:
                raise ValueError("32 règles au maximum")
        except ValueError as exc:
            self.message.setText(str(exc))
            return
        self.rules.append(FormatRule(FilterGroup("and", [Filter(0, "contains")])))
        self.refresh(len(self.rules) - 1)

    def remove(self):
        if self.current >= 0:
            del self.rules[self.current]
            self.refresh(min(self.current, len(self.rules) - 1))

    def move(self, direction):
        destination = self.current + direction
        if self.current < 0 or not 0 <= destination < len(self.rules):
            return
        try:
            self.store()
        except ValueError as exc:
            self.message.setText(str(exc))
            return
        self.rules[self.current], self.rules[destination] = self.rules[destination], self.rules[self.current]
        self.refresh(destination)

    def accept(self):
        try:
            self.store()
            from fireblade.core.rule_store import RuleBook
            RuleBook(self.headers,self.rules,self.functions).validate()
        except ValueError as exc:
            self.message.setText(str(exc))
            return
        super().accept()
