import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QFileDialog

from fireblade.core.engine import Case
from fireblade.core.models import View
from fireblade.core.sessions import read_session
from fireblade.ui.app import Window
from fireblade.ui.investigation_tools import ReportDialog


def settle(app,window):
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        app.processEvents()
        if not window.jobs and not window.pool.activeThreadCount() and not window.tabs.pending and (window.model is None or not window.model.jobs):return
        time.sleep(.005)
    raise AssertionError('Operation did not settle')


def loaded(app,tmp_path):
    window=Window(investigation_root=tmp_path/'cases');window.show();errors=[];window.error=lambda value:errors.append(str(value))
    window.create_investigation('Case graphique')
    for n in range(2):
        source=tmp_path/f'events-{n}.csv'
        source.write_text('Timestamp,User,SourceIP,Description\n2026-01-01T00:00:00.000000001Z,alice,10.0.0.1,First\n2026-01-02T00:00:00Z,bob,10.0.0.2,Second\n2026-01-03T00:00:00Z,alice,10.0.0.1,Third\n')
        case=Case(tmp_path/f'analysis-{n}.timeline');case.import_csv(source);case.close()
        window.load_case(tmp_path/f'analysis-{n}.timeline');settle(app,window)
    assert not errors
    return window,errors


def test_autosave_retains_session_and_can_be_disabled(qt_application,tmp_path):
    window,errors=loaded(qt_application,tmp_path)
    try:
        window.set_view(View(search='alice'));settle(qt_application,window)
        window.autosave_investigation()
        data=window.active_investigation
        snapshots,active=read_session(window.investigation_library.session_path(data))
        assert snapshots[active].view.search=='alice'
        assert window.investigation_library.history(data['id'])
        revision=data['revision'];window.autosave_action.setChecked(False);window.autosave_investigation()
        assert window.active_investigation['revision']==revision and not errors
    finally:window.close();settle(qt_application,window)


def test_timeline_zoom_correlation_open_source_and_case_isolation(qt_application,tmp_path):
    window,errors=loaded(qt_application,tmp_path)
    try:
        window.show_timeline();panel=window.timeline_panel
        QTest.mouseClick(panel.build_button,Qt.LeftButton);settle(qt_application,window)
        assert panel.store and panel.model.rowCount()==6
        assert sum(r[2] for r in panel.canvas.histogram['rows'])==6
        full=panel.bounds;panel.zoom(.5);settle(qt_application,window)
        assert panel.bounds[1]-panel.bounds[0] < full[1]-full[0]
        assert panel.overview.histogram['start']==full[0]
        panel.back();settle(qt_application,window);assert panel.bounds==full
        panel.query.setText('alice');panel.kind.setCurrentIndex(panel.kind.findData('user'));panel.exact.setChecked(True)
        QTest.mouseClick(panel.apply_button,Qt.LeftButton);settle(qt_application,window)
        assert panel.model.rowCount()==4
        assert all('alice' in row[4] for row in panel.model.rows)
        panel.isolate(1);settle(qt_application,window);assert panel.model.rowCount()==2
        row=panel.model.rows[0];expected_path=panel.documents[row[0]].path
        panel.table.setCurrentIndex(panel.model.index(0,0));QTest.mouseClick(panel.open_button,Qt.LeftButton);settle(qt_application,window)
        assert str(window.case.path)==expected_path and window.workbench.currentIndex()==0
        assert window.case.count(window.view)==1 and window.case.page(window.view)[0][0]==row[1]
        window.return_to_timeline();settle(qt_application,window)
        assert window.case.count(window.view)==3 and window.workbench.currentIndex()==window.timeline_tab_index
        window.create_investigation('Autre case');settle(qt_application,window)
        assert panel.store is None and panel.model.rowCount()==0 and panel.query.text()==''
        assert not errors
    finally:window.close();settle(qt_application,window)


def test_portable_case_actions_and_timeline_export(qt_application,tmp_path):
    window,errors=loaded(qt_application,tmp_path)
    try:
        window.case.bookmark(1,'Constat transportable')
        path=tmp_path/'portable.fireblade-case'
        window.export_investigation_package(path,include_sources=True);settle(qt_application,window)
        assert path.exists()
        window.import_investigation_package(path);settle(qt_application,window)
        cases,_=window.investigation_library.list();assert len(cases)==2
        imported=next(c for c in cases if c['id']!=window.active_investigation['id'])
        assert window.open_investigation(imported['id']);settle(qt_application,window)
        assert window.case.bookmarks()=={1:'Constat transportable'}
        window.show_timeline();panel=window.timeline_panel;panel.rebuild();settle(qt_application,window)
        panel.query.setText('alice');panel.apply_query();settle(qt_application,window)
        csv_path=tmp_path/'timeline.csv';panel.export_csv(csv_path);settle(qt_application,window)
        import csv
        with csv_path.open(encoding='utf-8-sig',newline='') as incoming:rows=list(csv.reader(incoming))
        assert len(rows)==5 and 'Constat transportable' in csv_path.read_text(encoding='utf-8-sig')
        assert not errors
    finally:window.close();settle(qt_application,window)


def test_report_pdf_is_built_by_worker_from_ui(qt_application,tmp_path,monkeypatch):
    window,errors=loaded(qt_application,tmp_path)
    try:
        window.case.bookmark(1,'Constat PDF')
        window.show_timeline();window.timeline_panel.rebuild();settle(qt_application,window)
        def accept(dialog):dialog.timeline.setChecked(True);return QDialog.Accepted
        monkeypatch.setattr(ReportDialog,'exec',accept)
        pdf=tmp_path/'report.pdf'
        monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args,**kwargs:(str(pdf),'Rapport PDF (*.pdf)'))
        window.export_investigation_report();settle(qt_application,window)
        assert pdf.exists() and pdf.read_bytes().startswith(b'%PDF-')
        assert b'/Subtype /Image' in pdf.read_bytes()
        assert '1 constats' in window.statusBar().currentMessage()
        assert not errors
    finally:window.close();settle(qt_application,window)


def test_timeline_filters_and_period_survive_case_reopening(qt_application,tmp_path):
    window,errors=loaded(qt_application,tmp_path)
    try:
        identifier=window.active_investigation['id'];window.show_timeline();panel=window.timeline_panel
        panel.rebuild();settle(qt_application,window)
        panel.query.setText('alice');panel.kind.setCurrentIndex(panel.kind.findData('user'));panel.exact.setChecked(True)
        panel.apply_query();settle(qt_application,window);panel.zoom(.4);settle(qt_application,window)
        bounds=panel.bounds;count=panel.model.rowCount()
        assert window.close_investigation();settle(qt_application,window)
        assert window.open_investigation(identifier);settle(qt_application,window)
        window.show_timeline();panel.rebuild();settle(qt_application,window)
        assert panel.query.text()=='alice' and panel.kind.currentData()=='user' and panel.exact.isChecked()
        assert panel.bounds==bounds and panel.model.rowCount()==count
        # A context-menu request must replace the saved query on a fresh index.
        panel.reset_workspace();panel.correlate('bob','user');settle(qt_application,window)
        assert panel.applied_filters['text']=='bob' and panel.model.rowCount()==2
        assert not errors
    finally:window.close();settle(qt_application,window)


def test_timeline_panel_fits_small_window(qt_application,tmp_path):
    window,errors=loaded(qt_application,tmp_path)
    try:
        window.resize(1024,600);window.show_timeline();settle(qt_application,window)
        assert window.width()<=1024
        assert window.height()<=600
        assert window.timeline_panel.canvas.width()>=520
    finally:window.close();settle(qt_application,window)
