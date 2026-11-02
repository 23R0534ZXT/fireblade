"""Visual Boolean condition cards shared by filters and formatting rules."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget, QSizePolicy,
)

from fireblade.core.models import Filter, FilterGroup, OPERATORS


def button(text, callback, parent=None):
    control = QPushButton(text, parent)
    control.setCursor(Qt.PointingHandCursor)
    control.clicked.connect(callback)
    return control


class ConditionRow(QFrame):
    def __init__(self, editor, condition, owner=None, inverted=False):
        super().__init__()
        self.editor, self.owner = editor, owner
        self.setObjectName("conditionRow")
        self.setStyleSheet("QFrame#conditionRow { background: palette(base); border: 1px solid palette(mid); border-radius: 6px; }")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.column = QComboBox()
        self.column.addItems(editor.headers)
        self.column.setCurrentIndex(condition.column)
        self.column.setAccessibleName("Colonne de la condition")
        self.column.setMinimumContentsLength(10)
        self.column.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.operator = QComboBox()
        for label, code in OPERATORS:
            self.operator.addItem(label, code)
        self.operator.setCurrentIndex(self.operator.findData(condition.operator))
        self.operator.setAccessibleName("Comparaison")
        self.column.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.column.setMinimumWidth(80)
        self.operator.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.operator.setMinimumWidth(100)
        self.text = QLineEdit(condition.value)
        self.text.setPlaceholderText("Valeur à rechercher…")
        self.text.setAccessibleName("Valeur de la condition")
        self.inverse = QCheckBox("Exclure (NON)")
        self.inverse.setToolTip("Inverse uniquement cette condition (NON).")
        self.inverse.setChecked(inverted)
        remove = button("×", lambda: editor.remove_node(self), self)
        remove.setFixedWidth(30)
        remove.setToolTip("Supprimer cette condition")
        remove.setAccessibleName("Supprimer cette condition")
        for control in (self.column, self.operator, self.text, remove):
            control.setMinimumHeight(30)
        layout.addWidget(self.column, 2)
        layout.addWidget(self.operator, 2)
        layout.addWidget(self.text, 3)
        layout.addWidget(self.inverse)
        layout.addWidget(remove)
        self.column.currentIndexChanged.connect(editor.changed)
        self.operator.currentIndexChanged.connect(self.update_operator)
        self.text.textChanged.connect(editor.changed)
        self.inverse.toggled.connect(editor.changed)
        self.update_operator()

    def update_operator(self, *_):
        needs_value = self.operator.currentData() not in ("empty", "not_empty")
        self.text.setEnabled(needs_value)
        self.text.setPlaceholderText("Valeur à rechercher…" if needs_value else "Aucune valeur nécessaire")
        self.editor.changed()

    def value(self, depth=0):
        if depth > 24:
            raise ValueError("24 niveaux au maximum")
        result = Filter(self.column.currentIndex(), self.operator.currentData(), self.text.text())
        return FilterGroup("not", [result]) if self.inverse.isChecked() else result


class ConditionGroup(QFrame):
    def __init__(self, editor, condition, owner=None):
        super().__init__()
        self.editor, self.owner, self.children = editor, owner, []
        self.setObjectName("conditionGroup")
        self.direct_not = condition.logic == "not"
        inverted = self.direct_not
        if inverted and len(condition.children) == 1 and isinstance(condition.children[0], FilterGroup) and condition.children[0].logic in ("and", "or"):
            condition = condition.children[0]
            self.direct_not = False
        self.layout_box = QVBoxLayout(self)
        self.layout_box.setContentsMargins(14, 12, 14, 12)
        self.layout_box.setSpacing(10)
        heading = QHBoxLayout()
        self.badge = QLabel()
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setFixedWidth(52)
        heading.addWidget(self.badge)
        title = QLabel("Filtrer les lignes" if owner is None else "Sous-groupe")
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        heading.addWidget(title)
        heading.addStretch()
        self.fold = button('Replier', self.toggle_fold, self)
        self.fold.setCheckable(True)
        self.fold.setAccessibleName('Replier ou déplier ce groupe de conditions')
        heading.addWidget(self.fold)
        if owner is not None:
            remove = button("Supprimer le groupe", lambda: editor.remove_node(self), self)
            heading.addWidget(remove)
        self.layout_box.addLayout(heading)
        options = QHBoxLayout()
        self.all_button = button("Toutes les conditions", lambda: self.select_logic("and"), self)
        self.any_button = button("Au moins une", lambda: self.select_logic("or"), self)
        self.logic_buttons = QButtonGroup(self)
        for control in (self.all_button, self.any_button):
            control.setCheckable(True)
            control.setProperty("logicChoice", True)
            control.setMinimumHeight(32)
            self.logic_buttons.addButton(control)
            options.addWidget(control)
        (self.any_button if condition.logic == "or" else self.all_button).setChecked(True)
        options.addStretch()
        self.inverse = QCheckBox("Inverser le groupe (NON)")
        self.inverse.setChecked(inverted)
        self.inverse.setToolTip("Garde les lignes qui ne correspondent pas à ce groupe.")
        self.inverse.toggled.connect(self.update_logic)
        options.addWidget(self.inverse)
        self.options_widget=QWidget();self.options_widget.setLayout(options)
        self.layout_box.addWidget(self.options_widget)
        self.explanation = QLabel()
        self.explanation.setWordWrap(True)
        self.layout_box.addWidget(self.explanation)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(8, 0, 0, 0)
        self.body.setSpacing(7)
        self.body_widget=QWidget();self.body_widget.setLayout(self.body)
        self.layout_box.addWidget(self.body_widget)
        self.empty = QLabel("Aucune condition. Ajoutez une condition pour commencer.")
        self.empty.setWordWrap(True)
        self.body.addWidget(self.empty)
        actions = QHBoxLayout()
        self.add_condition_button = button("+ Condition", lambda: editor.add_node(self, Filter(0, "contains")), self)
        self.add_group_button = button("+ Sous-groupe", lambda: editor.add_node(self, FilterGroup()), self)
        actions.addWidget(self.add_condition_button)
        actions.addWidget(self.add_group_button)
        actions.addStretch()
        self.actions_widget=QWidget();self.actions_widget.setLayout(actions)
        self.layout_box.addWidget(self.actions_widget)
        for child in condition.children:
            editor.add_node(self, child, notify=False)
        self.update_logic()

    def toggle_fold(self):
        folded=self.fold.isChecked()
        self.fold.setText('Déplier' if folded else 'Replier')
        for widget in (self.options_widget,self.body_widget,self.actions_widget):widget.setVisible(not folded)
        self.explanation.setVisible(not folded)
        self.editor.changed()

    @property
    def logic(self):
        return "or" if self.any_button.isChecked() else "and"

    def select_logic(self, logic):
        (self.any_button if logic == "or" else self.all_button).setChecked(True)
        self.direct_not = False
        self.update_logic()

    def update_logic(self, *_):
        inverse = self.inverse.isChecked()
        label = "NON" if inverse else "OU" if self.logic == "or" else "ET"
        self.badge.setText(label)
        self.badge.setStyleSheet("border: 1px solid palette(mid); border-radius: 5px; padding: 5px; font-weight: bold;")
        self.setStyleSheet('QFrame#conditionGroup { background: palette(alternate-base); border: 1px solid palette(mid); border-radius: 8px; } QPushButton[logicChoice="true"] { padding: 3px 12px; border: 1px solid palette(mid); border-radius: 5px; } QPushButton[logicChoice="true"]:checked { background: palette(midlight); font-weight: bold; }')
        if inverse:
            text = "Écarter les lignes qui respectent toutes ces conditions." if self.logic == "and" else "Écarter les lignes qui respectent au moins une de ces conditions."
        else:
            text = "Chaque condition doit être respectée." if self.logic == "and" else "Une seule condition respectée suffit."
        self.explanation.setText(text)
        self.editor.changed()

    def refresh_children(self):
        while self.body.count():
            item = self.body.takeAt(0)
            if item.widget() and item.widget() not in self.children and item.widget() is not self.empty:
                item.widget().hide()
                item.widget().deleteLater()
        self.empty.setVisible(not self.children)
        if not self.children:
            self.body.addWidget(self.empty)
        for index, child in enumerate(self.children):
            if index:
                connector = QLabel("OU" if self.logic == "or" else "ET")
                connector.setContentsMargins(14, 0, 0, 0)
                self.body.addWidget(connector)
            self.body.addWidget(child)
            child.show()

    def value(self, depth=0):
        if depth > 24:
            raise ValueError("24 niveaux au maximum")
        children = [child.value(depth + 1) for child in self.children]
        if self.direct_not and self.inverse.isChecked() and len(children) == 1:
            return FilterGroup("not", children)
        result = FilterGroup(self.logic, children)
        return FilterGroup("not", [result]) if self.inverse.isChecked() else result
