import time

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from fireblade.core.engine import Case
from fireblade.core.preferences import load_preferences, save_preferences
from fireblade.ui.app import Window
from fireblade.ui.preferences_dialog import PreferencesDialog
from fireblade.ui.text_matches import match_ranges


def settle(app, window):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        app.processEvents()
        if not window.jobs and not window.pool.activeThreadCount() and (not window.model or not window.model.jobs):return
        time.sleep(.005)
    pytest.fail('Work did not finish')


def add_case(window, tmp_path, name, user='alice'):
    source = tmp_path/(name+'.csv')
    source.write_text(f'Time,Artifact,User,Path\n2026-11-04T10:00:00Z,{name},{user},C:/users/{user}\n')
    case = Case(tmp_path/(name+'.timeline'));case.import_csv(source)
    window.detach();window.attach(case)


def test_detach_attach_and_restore_panel_geometry(qt_application, tmp_path):
    window = Window(require_case=False);window.show()
    index = window.timeline_tab_index;page = window.workbench.widget(index)
    try:
        dock = window.workbench.detach_panel(index)
        assert dock.widget() is page and window.workbench.indexOf(page) == index
        window.workbench.setCurrentWidget(page)
        assert window.workbench.currentIndex() == index
        window.workspace_layout.save()
        window.workbench.attach_panel(index)
        assert window.workbench.widget(index) is page and index not in window.workbench.panels
        window.workspace_layout.restore()
        assert index in window.workbench.panels
        window.workspace_layout.reset()
        assert not window.workbench.panels
    finally:window.close()


def test_focus_gives_timeline_space_and_restores_analysis(qt_application, tmp_path):
    window = Window(require_case=False);window.show()
    try:
        add_case(window, tmp_path, 'EVTX');settle(qt_application,window)
        window.workspace_layout.timeline();settle(qt_application,window)
        assert window.timeline_panel.store.page()['count'] == 1
        assert window.timeline_panel.store.sources[0]['dated'] == 1
        assert window.workbench.tabBar().isHidden()
        assert window.main_toolbar.isHidden()
        assert window.timeline_panel.canvas.height() >= 290
        window.workspace_layout.analysis();settle(qt_application,window)
        assert not window.workbench.tabBar().isHidden() and window.workbench.currentIndex() == 0
        window.workspace_layout.side_by_side();settle(qt_application,window)
        assert window.timeline_tab_index in window.workbench.panels
        assert window.workbench.currentIndex() == 0
        assert window.case.count(window.view) == 1
        window.workspace_layout.reset()
    finally:settle(qt_application,window);window.close()


def test_global_search_reaches_inactive_artifacts_and_opens_source(qt_application,tmp_path):
    window = Window(require_case=False);window.show()
    try:
        for name, user in [('EVTX','alice'),('MFT','bob'),('Prefetch','alice')]:
            add_case(window,tmp_path,name,user);settle(qt_application,window)
        assert window.search_scope.currentData() == 'all'
        window.search.setText('alice');window.search_workspace_or_active();settle(qt_application,window)
        panel = window.search_panel
        assert [r.count for r in panel.results] == [1,0,1]
        assert panel.table.isRowHidden(1)
        panel.open_result(0,0);settle(qt_application,window)
        assert window.case.info['path'].endswith('EVTX.csv') and window.view.search == 'alice'
    finally:settle(qt_application,window);window.close()


def test_resources_are_validated_saved_and_applied_to_live_queries(qt_application,tmp_path):
    window = Window(require_case=False)
    try:
        add_case(window,tmp_path,'EVTX');settle(qt_application,window)
        dialog = PreferencesDialog(window.preferences, window)
        dialog.memory.setValue(192);dialog.query_threads.setValue(2);dialog.parsing_threads.setValue(3)
        dialog.accept();save_preferences(dialog.preferences)
        window.preferences = load_preferences();window.apply_preferences()
        assert window.settings.threads == 2 and window.preferences.parsing_threads == 3
        assert window.case.db.execute("SELECT current_setting('threads')").fetchone()[0] == 2
        assert window.settings.memory_mb == 192
        dialog.deleteLater()
    finally:window.close()


def test_column_drag_is_saved_without_closing_artifact(qt_application,tmp_path):
    from fireblade.core.auto_layout import load_auto_layout
    window = Window(require_case=False)
    try:
        add_case(window,tmp_path,'EVTX');settle(qt_application,window)
        header = window.tree.header();header.moveSection(header.visualIndex(4),1)
        QTest.qWait(850)
        saved, _path = load_auto_layout(window.case.headers,window.case.info)
        assert saved is not None and saved.view.header_state
        add_case(window,tmp_path,'OtherEVTX');settle(qt_application,window)
        assert window.tree.header().visualIndex(4) == 1
    finally:window.close()


def test_occurrence_ranges_support_repetition_case_and_unicode():
    assert match_ranges('alice ALICE bob', ['alice']) == [(0,5),(6,5)]
    assert match_ranges('😀 alice', ['alice']) == [(3,5)]
    assert match_ranges('bob', ['alice']) == []


def test_navigation_groups_artifacts_without_reading_databases(qt_application,tmp_path):
    window = Window(require_case=False)
    try:
        add_case(window,tmp_path,'Prefetch');settle(qt_application,window)
        assert window.navigator.grouping.currentData() == 'families'
        labels = [item.text(0) for item in window.navigator.items()]
        assert 'Exécution (1)' in labels and 'Prefetch.csv' in labels
        window.workspace_layout.detach_auxiliary('artifacts',window.navigator,window.workspace_splitter)
        window.workspace_layout.detach_auxiliary('details',window.details,window.splitter)
        assert len(window.workspace_layout.auxiliary) == 2
        window.workspace_layout.reset()
        assert window.workspace_splitter.indexOf(window.navigator) >= 0
        assert window.splitter.indexOf(window.details) >= 0
    finally:window.close()


def test_columns_dialog_reorders_hides_and_saves(qt_application,tmp_path):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QListWidget, QDialogButtonBox
    window = Window(require_case=False)
    try:
        add_case(window,tmp_path,'EVTX');settle(qt_application,window)
        def edit():
            dialog = QApplication.activeModalWidget()
            listing = dialog.findChild(QListWidget)
            listing.insertItem(0,listing.takeItem(3))
            listing.item(2).setCheckState(Qt.Unchecked)
            QTest.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok),Qt.LeftButton)
        QTimer.singleShot(50,edit);window.columns()
        assert window.tree.header().visualIndex(4) == 1
        assert window.tree.isColumnHidden(2)
        add_case(window,tmp_path,'AnotherEVTX');settle(qt_application,window)
        assert window.tree.header().visualIndex(4) == 1 and window.tree.isColumnHidden(2)
    finally:window.close()


def test_pinned_column_order_and_focus_survive_restart(qt_application,tmp_path):
    window = Window(require_case=False);window.show()
    add_case(window,tmp_path,'EVTX');settle(qt_application,window)
    window.pin_column(1);window.pin_column(2)
    panel = window.tree.frozen
    panel.header().moveSection(panel.header().visualIndex(3),1)
    assert window.view.pinned_columns == [2,1]
    window.workspace_layout.timeline();settle(qt_application,window)
    assert window.close()
    assert not window.jobs and not window.pool.activeThreadCount()
    restarted = Window(require_case=False);restarted.show()
    try:
        assert restarted.workspace_layout.focused
        restarted.workspace_layout.analysis()
        assert not restarted.main_toolbar.isHidden()
        assert restarted.workbench.currentIndex() == 0
    finally:restarted.close()


def test_narrow_timeline_wraps_controls_and_can_show_graph_only(qt_application,tmp_path):
    window = Window(require_case=False);window.resize(1400,900);window.show()
    try:
        add_case(window,tmp_path,'EVTX');settle(qt_application,window)
        window.workspace_layout.side_by_side();settle(qt_application,window)
        qt_application.processEvents()
        assert window.timeline_host.horizontalScrollBar().maximum() == 0
        panel = window.timeline_panel
        panel.events_visible.setChecked(False);qt_application.processEvents()
        assert panel.splitter.widget(1).isHidden()
        window.workspace_layout.timeline();settle(qt_application,window)
        assert panel.focus_button.text() == 'Rétablir'
        QTest.mouseClick(panel.focus_button,Qt.LeftButton)
        assert not window.workbench.tabBar().isHidden()
        assert panel.focus_button.text() == 'Agrandir'
    finally:settle(qt_application,window);window.close()


def test_rule_from_cell_targets_only_that_column(qt_application,tmp_path,monkeypatch):
    from fireblade.ui.advanced_dialogs import RulesDialog
    from PySide6.QtWidgets import QDialog
    from PySide6.QtGui import QColor
    window = Window(require_case=False)
    try:
        add_case(window,tmp_path,'EVTX');settle(qt_application,window)
        monkeypatch.setattr(RulesDialog,'exec',lambda self: QDialog.Accepted)
        window.rule_from_value(2,'alice');settle(qt_application,window)
        assert window.view.format_rules[-1].target == 2
        assert window.model.data(window.model.index(0,3),Qt.BackgroundRole) == QColor('#fff0b3')
        assert window.model.data(window.model.index(0,4),Qt.BackgroundRole) != QColor('#fff0b3')
    finally:window.close()


def test_columns_follow_format_across_cases_without_leaking_filters(qt_application,tmp_path):
    from fireblade.core.models import Filter
    first = Window(investigation_root=tmp_path/'cases',require_case=True)
    first.create_investigation('First')
    try:
        add_case(first,tmp_path,'EVTX');settle(qt_application,first)
        first.tree.header().moveSection(first.tree.header().visualIndex(4),1)
        first.view.filters=[Filter(2,'eq','alice')];first.apply();settle(qt_application,first)
        first.save_format_layout()
    finally:first.close()
    second = Window(investigation_root=tmp_path/'cases',require_case=True)
    second.create_investigation('Second')
    try:
        add_case(second,tmp_path,'OtherEVTX','bob');settle(qt_application,second)
        assert second.tree.header().visualIndex(4) == 1
        assert not second.view.filters and not second.view.search
        assert second.case.count(second.view) == 1
    finally:second.close()
