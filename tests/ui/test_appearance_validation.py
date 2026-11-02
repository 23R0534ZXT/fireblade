import pytest
from PySide6.QtTest import QTest
from fireblade.ui.advanced_dialogs import RulesDialog
from fireblade.validation.appearance import ensure_control_visible


@pytest.mark.parametrize('point_size', [10, 12, 15, 20])
def test_newly_revealed_rule_controls_are_scrolled_after_layout(qt_application, point_size):
    dialog = RulesDialog(['Artifact', 'User', 'ID'], [])
    font = dialog.font()
    font.setPointSize(point_size)
    dialog.setFont(font)
    dialog.show()
    QTest.qWait(80)
    try:
        dialog.add()
        dialog.target.setCurrentIndex(1)
        QTest.qWait(50)
        dialog.rule_steps.setCurrentIndex(2)
        dialog.advanced_button.setChecked(True)
        assert ensure_control_visible(qt_application, dialog.format_tabs.widget(0), dialog.all_source_rows)
        dialog.format_tabs.setCurrentIndex(1)
        dialog.visual.setCurrentIndex(dialog.visual.findData('icon'))
        dialog.icon_levels.setCurrentIndex(dialog.icon_levels.findData(5))
        for widget in (dialog.bound_mode, dialog.icon_colors[4], dialog.icon_floor):
            assert ensure_control_visible(qt_application, dialog.format_tabs.widget(1), widget)
    finally:
        dialog.close()
        dialog.deleteLater()
