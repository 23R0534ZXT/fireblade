import json
from PySide6.QtWidgets import QFileDialog
from tests.ui.test_investigation_tools import loaded,settle
from fireblade.core.coverage import load_state


def test_dashboard_audits_all_analyses_and_preserves_journal(qt_application,tmp_path):
    window,errors=loaded(qt_application,tmp_path)
    try:
        panel=window.coverage_panel;panel.open();panel.hashes.setChecked(True);panel.launch();settle(qt_application,window)
        assert panel.report and len(panel.report['sources'])==2 and panel.report['counts']['error']==0,errors
        assert all(s['read']==3 and s['dated']==3 for s in panel.report['sources'])
        assert 'SHA-256 recalculés' in panel.status.text()
        panel.record('Import','error','permission denied','/missing.csv')
        path=panel.state_path();assert load_state(path)['events'][-1]['stage']=='Import'
        panel.mode.setCurrentIndex(1);panel.filter();assert panel.model.rowCount()>=1
        assert any('droits' in e['action'] for e in panel.entries)
        panel.reset_workspace();panel.open();assert panel.events[-1]['reason']=='permission denied'
        assert not errors
    finally:window.close();settle(qt_application,window)


def test_failures_are_recorded_even_with_custom_error_handlers(qt_application,tmp_path):
    window,errors=loaded(qt_application,tmp_path)
    try:
        def broken():raise OSError('No space left on device')
        captured=[];window.run(broken,lambda _:None,on_error=captured.append,coverage_stage='Export',coverage_context='out.csv');settle(qt_application,window)
        event=window.coverage_panel.events[-1]
        assert event['stage']=='Export' and event['path']=='out.csv' and 'espace' in event['action'] and captured
        window.run(broken,lambda _:None,on_error=captured.append,coverage_stage='Chronologie');settle(qt_application,window)
        assert window.coverage_panel.events[-1]['stage']=='Chronologie'
    finally:window.close();settle(qt_application,window)


def test_export_verified_receipt_and_protected_journal(qt_application,tmp_path,monkeypatch):
    window,errors=loaded(qt_application,tmp_path)
    try:
        target=tmp_path/'export.csv';monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *_:(str(target),''))
        window.export_csv();settle(qt_application,window)
        entry=window.coverage_panel.events[-1]
        assert entry['stage']=='Export' and entry['metrics']['written']==3 and entry['metrics']['sha256']
        assert not window.investigation_destination_is_safe(window.coverage_panel.state_path())
        assert errors
    finally:window.close();settle(qt_application,window)


def test_unreadable_journal_is_not_silently_replaced(qt_application,tmp_path):
    window,errors=loaded(qt_application,tmp_path)
    try:
        panel=window.coverage_panel;path=panel.state_path();path.write_text('{invalid')
        panel.reset_workspace();panel.open();panel.record('Import','error','new incident')
        assert path.read_text()=='{invalid' and panel.persistence_error
        panel.launch();settle(qt_application,window)
        assert panel.report['counts']['error']>=1
    finally:window.close();settle(qt_application,window)


def test_saved_plan_report_and_cancelled_recheck_preserve_previous_result(qt_application,tmp_path,monkeypatch):
    from fireblade.core.errors import OperationCancelled
    from fireblade.core.coverage import load_report
    import fireblade.ui.coverage as module
    window,errors=loaded(qt_application,tmp_path)
    try:
        panel=window.coverage_panel;panel.open();panel.expected_tools=['EvtxECmd'];panel.launch();settle(qt_application,window)
        path=panel.state_path().with_name('coverage-last.json');assert load_report(path)['expected_readers']==['EvtxECmd']
        report=panel.report;previous=path.read_bytes()
        def cancelled(*_,**__):raise OperationCancelled()
        monkeypatch.setattr(module,'audit',cancelled);panel.launch();settle(qt_application,window)
        assert panel.report is report and path.read_bytes()==previous
        panel.reset_workspace();panel.open();assert panel.expected_tools==['EvtxECmd'] and panel.report
        window.resize(1024,600);qt_application.processEvents();assert window.width()<=1024 and window.height()<=600
        assert not errors
    finally:window.close();settle(qt_application,window)
