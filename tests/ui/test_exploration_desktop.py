import copy
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from fireblade.core.engine import Case
from fireblade.core.models import Filter, Summary, View
from fireblade.ui.app import Window
from fireblade.ui.cross_search import WorkspaceSearch
from fireblade.ui.exploration_dialogs import GroupsDialog, DateFilterDialog


def settle(app, window, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if not window.jobs and not window.pool.activeThreadCount() and (window.model is None or not window.model.jobs):
            return
        time.sleep(.005)
    pytest.fail('background work did not settle')


@pytest.fixture
def window(qt_application, tmp_path):
    source = tmp_path/'evidence.csv'
    source.write_text('Artifact,User,ID,Flag,Time\nMFT,alice,001,TRUE,2026-01-01 12:00:00.1234567\nEVTX,bob,2,FALSE,2026-02-01 01:00:00\nMFT,alice,3,TRUE,2026-01-02 01:00:00\n')
    case = Case(tmp_path/'first.timeline')
    case.import_csv(source)
    w = Window()
    errors = []
    w.error = errors.append
    w.attach(case)
    w.show()
    settle(qt_application,w)
    yield w
    settle(qt_application,w)
    assert not errors
    assert w.close()


def test_pinned_cells_keep_one_model_and_restore_with_views(qt_application, window):
    window.pin_column(1)
    qt_application.processEvents()
    assert window.tree.pinned == [0,2]
    assert window.tree.frozen.isVisible()
    assert window.tree.frozen.model() is window.model
    assert window.tree.frozen.selectionModel() is window.tree.selectionModel()
    assert window.tree.isColumnHidden(2)
    assert 1 in window.visible_columns()
    assert window.tree.frozen.columnWidth(2) > 0
    view = copy.deepcopy(window.view)
    window.set_view(view)
    settle(qt_application,window)
    assert window.tree.pinned == [0,2]
    window.pin_column(1)
    assert not window.tree.frozen.isVisible()
    assert not window.tree.isColumnHidden(2)


def test_cross_search_uses_all_documents_not_only_active_or_loaded_rows(qt_application, window, tmp_path):
    first = window.case.path
    source = tmp_path/'second.csv'
    source.write_text('Other,User\nalice,bob\nalice,alice\n')
    case = Case(tmp_path/'second.timeline')
    case.import_csv(source)
    window.detach()
    window.attach(case)
    settle(qt_application,window)
    search = WorkspaceSearch(window.documents, window.settings, window.case)
    hits = search.find('alice')
    assert [h.count for h in hits] == [2,2]
    assert all(not h.error for h in hits)
    # A missing analysis is reported and not recreated as an empty database.
    window.documents[0].path = str(tmp_path/'missing.timeline')
    hits = WorkspaceSearch(window.documents, window.settings, window.case).find('alice')
    assert hits[0].count is None and hits[0].error
    assert not Path(window.documents[0].path).exists()
    window.documents[0].path = str(first)


def test_closed_tab_restores_notes_view_and_pins(qt_application, window):
    window.view.filters = [Filter(1,'eq','alice')]
    window.pin_column(1)
    window.apply()
    settle(qt_application,window)
    window.close_document(0)
    assert window.case is None and len(window.closed_documents) == 1
    window.reopen_closed()
    settle(qt_application,window)
    assert window.case.count(window.view) == 2
    assert window.view.pinned_columns == [1]
    assert not window.closed_documents


def test_boolean_presentation_and_timestamp_precision(qt_application, window):
    view = View(boolean_columns=[3],timestamp_columns=[4])
    window.set_view(view)
    settle(qt_application,window)
    window.model.date_format = 'iso7'
    assert window.model.data(window.model.index(0,4),Qt.CheckStateRole) == Qt.Checked
    assert window.model.data(window.model.index(1,4),Qt.CheckStateRole) == Qt.Unchecked
    assert window.model.data(window.model.index(0,5)).endswith('.1234567')
    assert window.model.node(window.model.index(0,0)).values[4] == 'TRUE'


def test_group_editor_and_date_period_drive_real_engine(qt_application, window):
    dialog = GroupsDialog(window.case.headers, window.view, window)
    dialog.add(Summary(2,'sum'))
    dialog.order.setCurrentIndex(dialog.order.findData('summary'))
    dialog.accept()
    view = dialog.view
    view.groups=[0]
    window.set_view(view)
    settle(qt_application,window)
    assert window.model.node(window.model.index(0,0)).values[0] == 'MFT'
    assert 'sum(ID)=4' in window.model.data(window.model.index(0,0))
    dates=DateFilterDialog()
    from PySide6.QtCore import QDate
    dates.date.setDate(QDate(2024,2,20))
    dates.interval.setCurrentIndex(dates.interval.findData('month'))
    assert dates.bounds() == ('2024-02-01','2024-03-01')
    dialog.deleteLater()
    dates.deleteLater()


def test_copy_follows_visible_order_and_preference(qt_application,window):
    window.tree.header().moveSection(window.tree.header().visualIndex(3),1)
    window.tree.setColumnHidden(2,True)
    window.tree.setCurrentIndex(window.model.index(0,0))
    window.copy_rows()
    text=QApplication.clipboard().text()
    assert text.splitlines()[0].startswith('ID\tArtifact\tFlag')
    window.preferences.copy_headers=False
    window.copy_rows()
    assert QApplication.clipboard().text().startswith('001\tMFT\tTRUE')


def test_multiline_tabs_and_dark_preferences_keep_readable_palette(qt_application,window):
    from PySide6.QtGui import QPalette
    for i in range(20):
        window.tabs.addTab(f'file-{i}-long-forensic-export.csv')
    window.preferences.multiline_tabs=True
    window.preferences.theme='dark'
    window.apply_preferences()
    qt_application.processEvents()
    assert len(window.tabs.rows)>1
    assert qt_application.palette().color(QPalette.Text).lightness()>180
    window.preferences.theme='light'
    window.apply_preferences()
    qt_application.processEvents()
    assert qt_application.palette().color(QPalette.Text).lightness()<80


def test_extended_acceptance_runs_real_desktop_paths(qt_application,window,tmp_path):
    from fireblade.validation.feature_checks import check_features
    completed=[]
    def expect(condition,message):
        assert condition,message
    def check(name,operation):
        operation()
        completed.append(name)
    check_features(window,tmp_path,lambda:settle(qt_application,window),check,expect,tmp_path)
    assert len(completed)==10
    assert (tmp_path/'extended-pinned.png').is_file()
    assert (tmp_path/'extended-dark.png').is_file()


def test_open_queue_waits_for_work_and_preserves_requested_order(qt_application,window,monkeypatch):
    seen=[]
    monkeypatch.setattr(window,'open_path',lambda path:seen.append(Path(path).name))
    window.busy=True
    window.queue_files(['first.csv','second.csv'])
    qt_application.processEvents()
    assert seen==[]
    window.busy=False
    deadline=time.monotonic()+2
    while len(seen)<2 and time.monotonic()<deadline:
        qt_application.processEvents();time.sleep(.01)
    assert seen==['first.csv','second.csv']


def test_hidden_pinned_column_is_removed_from_both_grids_and_export(qt_application,window):
    window.pin_column(1)
    assert window.visible_columns()[0]==1
    window.hide_column(1)
    qt_application.processEvents()
    assert 1 not in window.view.pinned_columns
    assert 1 not in window.visible_columns()
    assert not window.tree.frozen.isVisible()


def test_first_pin_after_hidden_view_receives_rows_renders_cell_text(qt_application,window):
    from fireblade.validation.appearance import rendered_contrast
    window.preferences.theme='dark'
    window.apply_preferences()
    qt_application.processEvents()
    window.pin_column(1)
    qt_application.processEvents()
    rect=window.tree.frozen.visualRect(window.model.index(0,2))
    assert rect.isValid() and rect.height()>0
    assert rendered_contrast(window.tree.frozen.viewport(),rect.adjusted(5,3,-5,-3))['ink_pixels']>=5
    window.preferences.theme='light'
    window.apply_preferences()


@pytest.mark.parametrize('wrapped',[False,True])
def test_actual_visible_tab_click_switches_analysis_and_preserves_state(qt_application,window,tmp_path,wrapped):
    from PySide6.QtTest import QTest
    first=window.case.path
    window.case.bookmark(1,'Keep this annotation')
    window.view.filters=[Filter(1,'eq','alice')]
    window.apply();settle(qt_application,window)
    source=tmp_path/'second.csv';source.write_text('ID\nsecond-analysis\n')
    case=Case(tmp_path/'second.timeline');case.import_csv(source)
    window.detach();window.attach(case);settle(qt_application,window)
    window.preferences.multiline_tabs=wrapped
    if wrapped:window.tabs.setFixedWidth(180)
    window.apply_preferences();qt_application.processEvents()
    if wrapped:assert len(window.tabs.rows)==2
    bar,local=window.tabs.tab_widget(0)
    QTest.mouseClick(bar,Qt.LeftButton,pos=bar.tabRect(local).center())
    settle(qt_application,window)
    assert window.case.path==first
    assert window.case.count(window.view)==2
    assert window.case.bookmarks()=={1:'Keep this annotation'}
    bar,local=window.tabs.tab_widget(1)
    QTest.mouseClick(bar,Qt.LeftButton,pos=bar.tabRect(local).center())
    settle(qt_application,window)
    assert window.case.path==tmp_path/'second.timeline'


def test_five_long_wrapped_tabs_remain_clickable_after_font_and_geometry_change(qt_application,tmp_path):
    from PySide6.QtTest import QTest
    names=['événements Windows.csv','deuxième.csv','preuve été.xlsx','colonnes réordonnées.csv','fonctions étendues.csv']
    w=Window();errors=[];w.error=errors.append;w.show()
    try:
        paths=[]
        for i,name in enumerate(names):
            source=tmp_path/name;source.write_text('ID\n'+str(i)+'\n')
            case=Case(tmp_path/(str(i)+'.timeline'));case.import_csv(source)
            w.detach();w.attach(case);settle(qt_application,w);paths.append(case.path)
        w.preferences.multiline_tabs=True;w.preferences.theme='dark';w.tabs.setFixedWidth(260)
        w.apply_preferences();qt_application.processEvents()
        for i in [0,4,1,3,2]:
            bar,local=w.tabs.tab_widget(i)
            rect=bar.tabRect(local).intersected(bar.rect())
            assert rect.isValid()
            QTest.mouseClick(bar,Qt.LeftButton,pos=rect.center());settle(qt_application,w)
            assert w.case.path==paths[i],(i,w.active_document,bar.geometry())
        assert not errors
    finally:
        w.preferences.theme='light';w.apply_preferences();settle(qt_application,w);w.close()
