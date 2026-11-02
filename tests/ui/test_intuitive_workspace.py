"""User gestures and persistence for the forensic workspace redesign."""
import time

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton, QMessageBox

from fireblade.core.collection import Collection, ToolPack
from fireblade.core.engine import Case
from fireblade.core.models import Filter, FormatRule, View
from fireblade.ui.app import Window
from fireblade.ui.collection_report import CollectionReport


def settle(app,window):
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        app.processEvents()
        if not window.jobs and not window.busy and not window.pool.activeThreadCount() and not window.tabs.pending and (window.model is None or not window.model.jobs):return
        time.sleep(.005)
    raise AssertionError('Workspace did not settle')


def load(window,folder):
    source=folder/'events.csv';source.write_text('Artifact,User,ID\nEVTX,alice,0001\nMFT,bob,0002\nEVTX,charlie,0003\n')
    case=Case(folder/'events.timeline');case.import_csv(source);case.close()
    window.load_case(folder/'events.timeline')
    return folder/'events.timeline'


def test_empty_case_has_both_entry_points_and_permanent_save(qt_application):
    window=Window();window.show()
    try:
        window.create_investigation('Enquête intuitive')
        assert window.workbench.currentIndex()==0
        assert 'Enquête intuitive' in window.welcome_title.text()
        labels={b.text() for b in window.findChildren(QPushButton) if b.isVisible()}
        assert {'Importer une collecte…','Ouvrir un export…'}<=labels
        assert window.save_case_action in window.main_toolbar.actions()
        window.save_case_action.trigger()
        assert window.last_case_save.text().startswith('Case enregistré à ')
        assert not window.hayabusa_action.isEnabled()
    finally:window.close()


def test_left_gutter_marks_entire_row_and_restores_without_losing_groups(qt_application,tmp_path):
    window=Window();window.show();path=load(window,tmp_path);settle(qt_application,window)
    try:
        view=View(groups=[0],format_rules=[FormatRule(Filter(1,'eq','alice'),target=1,background='#ff0000')])
        window.set_view(view);settle(qt_application,window)
        parent=next(window.model.index(i,0) for i in range(window.model.rowCount()) if window.model.node(window.model.index(i,0)).values[0]=='EVTX')
        window.tree.expand(parent);settle(qt_application,window)
        index=window.model.index(0,0,parent);row_id=window.model.node(index).values[0]
        # Click away from the checkbox: the complete gutter is a hit target.
        rect=window.tree.visualRect(index)
        QTest.mouseClick(window.tree.viewport(),Qt.LeftButton,pos=rect.topRight()+QPoint(-7,rect.height()//2))
        settle(qt_application,window)
        assert window.case.bookmarks()=={row_id:''}
        assert window.tree.isExpanded(parent)
        for column in range(window.model.columnCount()):
            assert window.model.index(0,column,parent).data(Qt.BackgroundRole)==QColor('#fff4c2')
        window.pin_column(1);settle(qt_application,window)
        assert window.tree.frozen.model() is window.model
        window.close_document(window.active_document);window.load_case(path);settle(qt_application,window)
        assert window.case.bookmarks()=={row_id:''}
    finally:window.close()


def test_removing_a_mark_with_a_note_requires_explicit_choice(qt_application,tmp_path,monkeypatch):
    window=Window();load(window,tmp_path);settle(qt_application,window)
    try:
        window.case.bookmark(1,'Ne pas perdre cette note');window.apply();settle(qt_application,window)
        monkeypatch.setattr(QMessageBox,'question',lambda *a,**kw:QMessageBox.No)
        window.mark_row(1,False)
        assert window.case.bookmarks()=={1:'Ne pas perdre cette note'}
        monkeypatch.setattr(QMessageBox,'question',lambda *a,**kw:QMessageBox.Yes)
        window.mark_row(1,False);settle(qt_application,window)
        assert window.case.bookmarks()=={}
    finally:window.close()


def test_clear_filters_keeps_presentation_and_full_reset_is_separate(qt_application,tmp_path):
    window=Window();window.show();load(window,tmp_path);settle(qt_application,window)
    try:
        window.set_view(View(groups=[0],sort_column=2,pinned_columns=[1],filters=[Filter(1,'eq','alice')],
                             format_rules=[FormatRule(Filter(0,'eq','EVTX'))]));settle(qt_application,window)
        next(b for b in window.findChildren(QPushButton) if b.text()=='Effacer les filtres').click()
        settle(qt_application,window)
        assert not window.view.filters
        assert window.view.groups==[0] and window.view.sort_column==2
        assert window.view.pinned_columns==[1] and len(window.view.format_rules)==1
        view_menu=next(a.menu() for a in window.menuBar().actions() if a.text()=='&Affichage')
        next(a for a in view_menu.actions() if a.text()=='Réinitialiser la vue').trigger()
        settle(qt_application,window)
        assert not window.view.groups and not window.view.pinned_columns
    finally:window.close()


def test_case_search_reuses_metadata_cache_and_refresh_sees_external_change(qt_application,monkeypatch):
    window=Window();calls=[]
    try:
        window.investigation_library.create('Alice')
        original=window.investigation_library.list
        def count():calls.append(True);return original()
        monkeypatch.setattr(window.investigation_library,'list',count)
        window.refresh_investigations()
        for value in ('a','al','ali','alice',''):window.cases_search.setText(value)
        assert len(calls)==1
        window.investigation_library.create('Bob')
        assert window.cases_table.rowCount()==1
        window.refresh_investigations()
        assert window.cases_table.rowCount()==2 and len(calls)==2
        assert window.case is None
    finally:window.close()


def test_collection_report_filters_statuses_and_keeps_exact_diagnostics(qt_application):
    panel=CollectionReport();panel.show()
    report=dict(source='evidence',output='work',status='complete',documents=[],files=[
        dict(path='A.evtx',status='complete',tools=['EvtxECmd']),
        dict(path='B.dat',status='attention',tools=['Shellbags'],sha256='abc',runs=[
            dict(tool='Shellbags',status='complete_with_warnings',warnings=['Ruche sale'],outputs=[])]),
        dict(path='C.bin',status='error',tools=[],error='Illisible'),
        dict(path='D.dat',status='attention',tools=['RECmd'],runs=[dict(tool='RECmd',status='error',error='Ruche illisible')])])
    try:
        panel.set_report(report,'Bilan complet de démonstration')
        assert panel.proxy.rowCount()==4
        panel.status.setCurrentIndex(panel.status.findData('warnings'))
        assert panel.proxy.rowCount()==1
        panel.table.setCurrentIndex(panel.proxy.index(0,0))
        assert 'Ruche sale' in panel.details.toPlainText() and 'abc' in panel.details.toPlainText()
        panel.status.setCurrentIndex(0);panel.search.setText('EVTX')
        assert panel.proxy.rowCount()==1
        panel.status.setCurrentIndex(panel.status.findData('errors'))
        assert panel.proxy.rowCount()==0
        panel.search.clear()
        assert panel.proxy.rowCount()==2
        assert '2 erreurs/interrompus' in panel.summary.text()
        assert panel.toPlainText()=='Bilan complet de démonstration'
    finally:
        panel.close();panel.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_navigation_uses_snapshots_and_groups_collections(qt_application,tmp_path,monkeypatch):
    window=Window();load(window,tmp_path);settle(qt_application,window)
    try:
        def forbidden(*a,**kw):raise AssertionError('Navigation opened a database')
        monkeypatch.setattr('fireblade.ui.workspace.Case',forbidden)
        window.refresh_navigation()
        leaves=[item for item in window.navigator.items() if item.data(0,Qt.UserRole) is not None]
        assert len(leaves)==1
        window.navigator.search.setText('events')
        assert not leaves[0].isHidden()
        window.navigator.search.setText('absent')
        assert leaves[0].isHidden()
        window.navigation_action.setChecked(False)
        assert window.navigator.isHidden()
    finally:window.close()


def test_hayabusa_is_disabled_for_text_collection_and_enabled_for_parsed_evtx(qt_application,tmp_path):
    source=tmp_path/'evidence';source.mkdir()
    window=Window()
    try:
        window.collection=Collection(source,tmp_path/'work',ToolPack(tmp_path/'pack'))
        report=window.collection.report;report['status']='complete'
        report['files']=[dict(path='linux.txt',status='complete',tools=['CatScale'])]
        window.show_collection_report(report)
        assert not window.hayabusa_button.isEnabled()
        report['files'].append(dict(path='System.evtx',status='complete',tools=['EvtxECmd']))
        window.show_collection_report(report)
        assert window.hayabusa_button.isEnabled()
        report['files'][-1].update(status='attention',runs=[dict(tool='EvtxECmd',status='complete_with_warnings',outputs=[dict(analysis='events.timeline')])])
        window.show_collection_report(report)
        assert window.hayabusa_button.isEnabled()
        window.busy=True;window.update_collection_controls()
        assert not window.hayabusa_action.isEnabled()
    finally:window.busy=False;window.close()
