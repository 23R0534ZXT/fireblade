from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialogButtonBox, QPushButton

from fireblade.core.engine import Case
from fireblade.core.models import Filter, FilterGroup, View
from fireblade.ui.advanced_dialogs import ExpressionEditor, FilterDialog
from fireblade.ui.theme import apply_theme


def test_card_buttons_build_apply_and_remove_nested_filter(qt_application, tmp_path):
    source = tmp_path / 'data.csv'
    source.write_text('User,EventID\nalice,4624\nalice,4625\nbob,4624\n')
    case = Case(tmp_path / 'data.timeline')
    case.import_csv(source)
    dialog = FilterDialog(case.headers, FilterGroup())
    dialog.show()
    qt_application.processEvents()
    editor = dialog.editor
    try:
        QTest.mouseClick(editor.root.add_condition_button, Qt.LeftButton)
        row = editor.root.children[0]
        QTest.keyClicks(row.text, 'alice')
        editor.root.add_group_button.click()
        group = editor.root.children[1]
        group.any_button.click()
        group.add_condition_button.click()
        nested = group.children[0]
        nested.column.setCurrentIndex(1)
        nested.operator.setCurrentIndex(nested.operator.findData('eq'))
        nested.text.setText('4624')
        expected = FilterGroup('and', [Filter(0, 'contains', 'alice'), FilterGroup('or', [Filter(1, 'eq', '4624')])])
        assert editor.value() == expected
        assert 'alice' in editor.preview.text() and '4624' in editor.preview.text()
        assert group.badge.text() == 'OU'
        assert case.count(View(expression=editor.value())) == 1
        group.inverse.setChecked(True)
        assert group.badge.text() == 'NON'
        assert case.page(View(expression=editor.value()))[0][2] == '4625'
        group.inverse.setChecked(False)
        nested.inverse.setChecked(True)
        assert case.count(View(expression=editor.value())) == 1
        editor.remove_node(group)
        assert case.count(View(expression=editor.value())) == 2
        buttons = dialog.findChild(QDialogButtonBox)
        QTest.mouseClick(buttons.button(QDialogButtonBox.Ok), Qt.LeftButton)
        assert dialog.result() == 1
        assert dialog.expression == FilterGroup('and', [Filter(0, 'contains', 'alice')])
    finally:
        dialog.close()
        case.close()


def test_empty_value_operators_and_exclusions_roundtrip(qt_application):
    expression = FilterGroup('not', [FilterGroup('or', [Filter(0, 'empty'), FilterGroup('not', [Filter(0, 'eq', 'alice')])])])
    editor = ExpressionEditor(['User'], expression)
    try:
        assert editor.value() == expression
        assert editor.root.badge.text() == 'NON'
        row = editor.root.children[0]
        assert not row.text.isEnabled()
        row.operator.setCurrentIndex(row.operator.findData('contains'))
        assert row.text.isEnabled()
        editor.remove_node(editor.root.children[1])
        editor.remove_node(row)
        assert editor.root.empty.isVisibleTo(editor.root)
        editor.root.add_condition_button.click()
        assert len(editor.root.children) == 1
    finally:
        editor.close()


def test_cards_support_dark_theme_and_display_untrusted_values_as_text(qt_application):
    try:
        apply_theme(qt_application, 'dark')
        editor = ExpressionEditor(['User'], FilterGroup('and', [Filter(0, 'contains', '<b>alice</b>')]))
        editor.resize(900, 480)
        editor.show()
        qt_application.processEvents()
        assert editor.preview.textFormat() == Qt.PlainText
        assert '<b>alice</b>' in editor.preview.text()
        assert editor.grab().width() == editor.width()
        assert editor.root.all_button.isChecked()
        editor.close()
    finally:
        apply_theme(qt_application)
