import csv
from pathlib import Path
import shutil
import time

from fireblade.core.collection import Collection,ToolPack
from fireblade.core.models import Filter
from fireblade.ui.app import Window


def settle(app,window,predicate=lambda:True):
    end=time.monotonic()+15
    while time.monotonic()<end:
        app.processEvents()
        if predicate() and not window.jobs and not window.pool.activeThreadCount() and window.model and not window.model.jobs:return
        time.sleep(.01)
    raise AssertionError('Context desktop did not settle')


def prepare_collection(tmp_path):
    source=tmp_path/'evidence';source.mkdir();artifact=source/'System.evtx';artifact.write_bytes(b'ElfFile\0')
    output=tmp_path/'work';output.mkdir();(output/'results').mkdir();(output/'analyses').mkdir()
    collection=Collection(source,output,ToolPack(tmp_path/'pack'))
    data=output/'results'/'events.csv'
    with data.open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['EventRecordId','TimeCreated','EventId','Computer','Channel','MapDescription','Payload'])
        writer.writerows([['41','2026-11-02 10:00:00','7001','PC01','System','Before','first'],['42','2026-11-02 10:01:00','104','PC01','System','Log cleared','full evidence'],['43','2026-11-02 10:02:00','7040','PC01','System','Service disabled','after']])
    raw=collection.import_result(data,'EvtxECmd')
    collection.report['files']=[dict(path=str(artifact),tools=['EvtxECmd'],status='complete',runs=[dict(tool='EvtxECmd',status='complete',outputs=[dict(csv=str(data),analysis=raw)])])]
    alerts=output/'results'/'Alertes Hayabusa.csv'
    with alerts.open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['Timestamp','RuleTitle','Level','Computer','EventID','RecordID','RuleID','Fireblade_EVTX_Source'])
        writer.writerow(['2026-11-02T10:01:00Z','Log cleared','high','PC01','104','42','rule-1',str(artifact)])
    alert_path=collection.import_result(alerts,'Hayabusa')
    collection.report['detection']=dict(status='complete',analysis=alert_path,outputs=[dict(analysis=alert_path)])
    collection.save()
    return collection,raw,alert_path


def test_alert_context_original_and_return_keep_alert_filters_and_notes(qt_application,tmp_path):
    collection,raw,alert_path=prepare_collection(tmp_path)
    window=Window(require_case=False);errors=[];window.error=errors.append
    try:
        window.collection=collection
        window.load_session(str(collection.output/'collection.fireblade-session'))
        settle(qt_application,window)
        window.load_case(alert_path);settle(qt_application,window)
        window.view.filters=[Filter(window.case.headers.index('Level'),'eq','high')]
        window.apply();settle(qt_application,window)
        window.case.bookmark(1,'À examiner')
        window.tree.setCurrentIndex(window.model.index(0,0))
        assert window.context_action.isEnabled() and window.context_open.isVisibleTo(window)
        window.context_open.click()
        settle(qt_application,window,lambda:window.context_preview is not None)
        assert str(window.case.path)==alert_path
        assert window.context_preview.model.rowCount()==3
        window.context_preview.keep.click()
        settle(qt_application,window,lambda:window.context_metadata() is not None)
        assert window.model.rowCount()==3
        role=window.case.headers.index('Relation à l’alerte')+1
        anchor=next(window.model.index(i,0) for i in range(3) if window.model.node(window.model.index(i,0)).values[role]=='Événement de l’alerte')
        window.tree.setCurrentIndex(anchor)
        window.context_source.click()
        settle(qt_application,window,lambda:window.case and str(window.case.path)==raw)
        assert window.model.rowCount()==1
        assert window.model.node(window.model.index(0,0)).values[1]=='42'
        window.context_return.click()
        settle(qt_application,window,lambda:window.case and str(window.case.path)==alert_path)
        assert window.view.filters==[Filter(window.case.headers.index('Level'),'eq','high')]
        assert window.case.bookmarks()=={1:'À examiner'}
        assert not errors
    finally:window.close()


def test_saved_context_reconnects_to_collection_without_raw_evtx(qt_application,tmp_path):
    from fireblade.core.alert_context import build_context
    from fireblade.core.engine import Case
    collection,raw,alert_path=prepare_collection(tmp_path)
    case=Case(alert_path)
    try:
        values=case.page(case_view())[0]
        alert=dict(zip(case.headers,values[1:]))
    finally:case.close()
    result=build_context(collection,alert,alert_path,1)
    shutil.rmtree(collection.root)
    window=Window(require_case=False);errors=[];window.error=errors.append
    try:
        assert window.collection is None
        window.load_case(result['analysis']);settle(qt_application,window)
        assert window.collection is not None
        assert window.context_metadata()['alert_row']==1
        assert window.view.sort_type=='timestamp'
        assert window.context_return.isVisibleTo(window)
        assert not errors
    finally:window.close()


def case_view():
    from fireblade.core.models import View
    return View()


def test_preview_reuses_panel_and_only_kept_context_enters_saved_session(qt_application,tmp_path):
    collection,raw,alert_path=prepare_collection(tmp_path)
    window=Window(require_case=False);errors=[];window.error=errors.append
    window.resize(1024,700);window.show()
    try:
        window.collection=collection;window.load_case(alert_path);settle(qt_application,window)
        window.tree.setCurrentIndex(window.model.index(0,0))
        before=len(collection.report['documents']);tabs=len(window.documents)
        window.preview_alert_context();settle(qt_application,window,lambda:window.context_preview is not None)
        first=window._preview_result['analysis']
        assert window.case.path==Path(alert_path) and len(window.documents)==tabs
        assert len(collection.report['documents'])==before
        assert not collection.report.get('contexts')
        assert window.context_preview.model.rowCount()==3
        assert window.width()<=1024
        assert window.navigator.isHidden()
        assert window.context_preview.selected()['Relation à l’alerte']=='Événement de l’alerte'
        window.preview_alert_context();settle(qt_application,window)
        assert window._preview_result['analysis']==first
        window.context_minutes.setValue(1);window.preview_alert_context()
        settle(qt_application,window)
        assert window._preview_result['analysis']!=first and not Path(first).exists()
        assert len(collection.report['documents'])==before
        window.keep_preview_context();settle(qt_application,window)
        kept=window.context_metadata();assert kept['minutes']==1
        assert len(collection.report['documents'])==before+1
        restored=Collection.reopen(collection.output,collection.pack)
        assert restored.report['contexts'][0]['analysis']==kept['analysis']
        assert not errors
    finally:window.close()


def test_preview_opens_verified_source_and_close_removes_only_unkept_files(qt_application,tmp_path):
    collection,raw,alert_path=prepare_collection(tmp_path)
    window=Window(require_case=False);errors=[];window.error=errors.append
    try:
        window.collection=collection;window.load_case(alert_path);settle(qt_application,window)
        window.tree.setCurrentIndex(window.model.index(0,0));window.preview_alert_context()
        settle(qt_application,window,lambda:window.context_preview is not None)
        preview=Path(window._preview_result['analysis'])
        window.context_preview.open_source.click()
        settle(qt_application,window,lambda:window.case.path==Path(raw))
        assert window.model.rowCount()==1 and window.model.node(window.model.index(0,0)).values[1]=='42'
        window.return_to_alerts();settle(qt_application,window)
        assert window.case.path==Path(alert_path)
        assert not errors
        assert window.close()
        assert not preview.exists() and Path(raw).exists() and Path(alert_path).exists()
    finally:window.close()


def test_alert_from_another_collection_cannot_use_current_collection(qt_application,tmp_path):
    collection,raw,alert_path=prepare_collection(tmp_path)
    window=Window(require_case=False);errors=[];window.error=errors.append
    try:
        window.collection=collection
        window.load_case(alert_path);settle(qt_application,window)
        window.tree.setCurrentIndex(window.model.index(0,0))
        assert window.context_action.isEnabled()
        other=tmp_path/'other';other.mkdir();evidence=other/'evidence';evidence.mkdir()
        window.collection=Collection(evidence,other/'work',ToolPack(other/'pack'))
        window.update_alert_context_bar()
        assert not window.context_action.isEnabled()
        window.open_alert_context()
        assert not window.jobs
        assert not window.collection.report.get('contexts')
        assert not errors
    finally:window.close()
