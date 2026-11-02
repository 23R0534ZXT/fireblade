import csv
import hashlib
import json
from pathlib import Path
import threading
import pytest
from fireblade.core.coverage import audit,event,digest,save_state,load_state,export_report,FORMAT
from fireblade.core.engine import Case
from fireblade.core.models import AnalysisSnapshot,View,Filter
from fireblade.core.workspace_reader import WorkspaceReader
from fireblade.core.errors import OperationCancelled,cancellation_scope


@pytest.fixture
def evidence(tmp_path):
    source=tmp_path/'source.csv';source.write_text('Timestamp,User,Empty\n2026-01-01T00:00:00Z,alice,\n2026-01-02T00:00:00,bob,\nbroken,carol,\n,david,\n')
    case=Case(tmp_path/'analysis.timeline');case.import_csv(source)
    doc=AnalysisSnapshot(str(case.path),case.info,View(search='absent'),b'')
    yield case,doc,source
    case.close()


def run(evidence,**options):
    case,doc,_=evidence
    return audit(WorkspaceReader([doc],active=case),**options)


def codes(report):return {i['code'] for i in report['findings']}


def test_dates_filters_empty_columns_and_hashes_are_explicit(evidence):
    case,doc,source=evidence;before=source.read_bytes();report=run(evidence,verify_hashes=True)
    assert {'source_verified','filtered_scope','empty_view','undated','naive_dates','empty_columns','no_inventory','timeline_not_built'}<=codes(report)
    stats=report['sources'][0];assert (stats['read'],stats['selected'],stats['dated'],stats['undated'],stats['naive'])==(4,0,2,2,1)
    assert stats['empty_dates']==1 and stats['invalid_dates']==1 and stats['invalid_samples']==[{'row_id':3,'value':'broken'}]
    assert stats['empty_columns']==['Empty'] and source.read_bytes()==before
    assert all(i['reason'] and i['action'] for i in report['findings'])


def test_changed_missing_source_and_database_are_not_reported_complete(evidence,tmp_path):
    case,doc,source=evidence;source.write_text(source.read_text().replace('alice','ALICE'))
    assert 'source_changed' in codes(run(evidence,verify_hashes=True))
    source.unlink();assert 'source_missing' in codes(run(evidence))
    doc.path=str(tmp_path/'missing.timeline');report=run(evidence)
    assert 'analysis_unreadable' in codes(report) and report['sources'][0]['read'] is None


def test_row_count_and_ids_corruption_are_detected(evidence):
    case,_,_=evidence
    case.db.execute('UPDATE events SET __row_id=1 WHERE __row_id=2')
    assert 'row_ids_invalid' in codes(run(evidence))
    case.db.execute('DELETE FROM events WHERE __row_id=3')
    assert 'row_mismatch' in codes(run(evidence))


def test_inventory_reader_outputs_closed_analyses_and_expected_families(evidence,tmp_path):
    case,doc,source=evidence;root=tmp_path/'collection';root.mkdir();(root/'unprocessed.evtx').touch()
    report=dict(source=str(root),output=str(tmp_path/'outputs'),status='cancelled',files=[dict(path=str(source),sha256=doc.source_info['sha256'],size=source.stat().st_size,status='attention',tools=['EvtxECmd'],runs=[dict(tool='EvtxECmd',status='error',error='permission denied',warnings=['partial output'],outputs=[dict(csv=str(tmp_path/'absent.csv'),analysis=str(tmp_path/'absent.timeline'))])])],documents=[dict(path=str(case.path)),dict(path=str(tmp_path/'absent.timeline'))])
    result=run(evidence,collections=[report],expected='windows')
    assert {'unfinished_collection','reader_problem','output_missing','missing_family','uninventoried_file','analysis_unreadable'}<=codes(result)
    assert 'EvtxECmd' in result['observed_readers']
    result=audit(WorkspaceReader([]),collections=[report]);assert 'closed_analysis' in codes(result)


def test_timeline_partial_stale_and_hunt_limits(evidence):
    case,doc,_=evidence
    timeline=dict(sources=[dict(path=doc.path,error='reader unavailable')],stale=True,respect_filters=True,include_undated=False)
    report=run(evidence,timeline=timeline,hunts=[dict(status='complete',truncated=True,rejected=1)])
    assert {'stale_timeline','partial_hunt','undated_hidden','analysis_unreadable'}<=codes(report)


@pytest.mark.parametrize('suffix',['csv','xlsx'])
def test_export_receipt_matches_file_filtered_rows_and_current_hash(evidence,tmp_path,suffix):
    case,doc,_=evidence;view=View(filters=[Filter(1,'eq','alice')]);target=tmp_path/f'export.{suffix}'
    receipt=case.export(target,view,columns=[0,1])
    assert receipt['written']==receipt['expected']==1 and receipt['source_rows']==4
    assert receipt['sha256']==hashlib.sha256(target.read_bytes()).hexdigest()
    if suffix=='csv':assert len(list(csv.reader(target.open(encoding='utf-8-sig'))))==2
    previous=event('Export','info','previous',str(target),sha256='0'*64)
    current=event('Export','info','current',str(target),**{k:v for k,v in receipt.items() if k!='path'})
    report=run(evidence,verify_hashes=True,events=[previous,current]);assert 'export_verified' in codes(report) and 'export_changed' not in codes(report)
    target.write_bytes(b'modified');assert 'export_changed' in codes(run(evidence,verify_hashes=True,events=[current]))


def test_export_count_mismatch_and_cancellation_preserve_destination(evidence,tmp_path,monkeypatch):
    case,_,_=evidence;target=tmp_path/'old.csv';target.write_text('previous')
    import fireblade.core.coverage as coverage
    def cancelled(*_):raise OperationCancelled()
    monkeypatch.setattr(coverage,'digest',cancelled)
    with pytest.raises(OperationCancelled):case.export(target,View())
    assert target.read_text()=='previous' and not target.with_name('old.csv.partial').exists()


def test_journal_and_atomic_exports_protect_sources(evidence,tmp_path):
    _,doc,source=evidence;state=dict(format=FORMAT,version=1,events=[event('Import','error','permission denied',str(source))],dropped=0)
    path=tmp_path/'coverage-state.json';save_state(path,state);assert load_state(path)==state
    assert 'droits' in state['events'][0]['action']
    report=run(evidence);target=tmp_path/'report.json';export_report(target,report);assert json.loads(target.read_text())['counts']==report['counts']
    with pytest.raises(ValueError):export_report(source,report)
    target.write_text('previous');cancel=threading.Event();cancel.set()
    with cancellation_scope(cancel),pytest.raises(OperationCancelled):export_report(target,report)
    assert target.read_text()=='previous'
    path.write_text('{invalid')
    with pytest.raises(ValueError):load_state(path)


def test_cancelled_audit_never_returns_partial_success(evidence):
    case,doc,_=evidence;reader=WorkspaceReader([doc],active=case)
    with pytest.raises(OperationCancelled):audit(reader,progress=lambda _:reader.interrupt())


def test_xlsx_empty_trailing_columns_are_verified_without_false_loss(evidence,tmp_path):
    case,_,_=evidence;receipt=case.export(tmp_path/'empty-columns.xlsx',View())
    assert receipt['verified_rows']==receipt['expected']==4


def test_wrong_values_with_same_row_count_never_replace_previous_export(evidence,tmp_path,monkeypatch):
    from openpyxl import Workbook
    import fireblade.core.spreadsheets as sheets
    case,_,_=evidence;target=tmp_path/'out.xlsx';target.write_bytes(b'previous')
    def broken_writer(path,headers,cursor,batch_size,checker):
        book=Workbook();sheet=book.active;sheet.append(headers)
        while rows:=cursor.fetchmany(batch_size):
            for row in rows:sheet.append(['wrong',*row[1:]])
        book.save(path);book.close()
    monkeypatch.setattr(sheets,'write_xlsx',broken_writer)
    with pytest.raises(ValueError,match='Contenu'):case.export(target,View())
    assert target.read_bytes()==b'previous'


def test_expected_families_can_be_narrowed_and_last_report_roundtrips(evidence,tmp_path):
    from fireblade.core.coverage import save_report,load_report
    report=run(evidence,expected='windows',expected_tools=['EvtxECmd'])
    missing=[item for item in report['findings'] if item['code']=='missing_family']
    assert len(missing)==1 and missing[0]['path']=='EvtxECmd'
    path=tmp_path/'coverage-last.json';save_report(path,report);assert load_report(path)==report


def test_timeline_annotations_are_checked_against_index_snapshot(evidence):
    from fireblade.core.timeline import TimelineStore
    case,doc,_=evidence;store=TimelineStore(memory_mb=64)
    try:
        store.build(WorkspaceReader([doc],active=case),{doc.path:0})
        snapshot=dict(sources=store.sources,stale=False)
        assert 'stale_timeline_annotations' not in codes(run(evidence,timeline=snapshot))
        case.bookmark(1,'New note after indexing')
        assert 'stale_timeline_annotations' in codes(run(evidence,timeline=snapshot))
    finally:store.close()


def test_pretty_printed_journal_size_is_checked_before_replacement(tmp_path,monkeypatch):
    import fireblade.core.coverage as module
    state=dict(format=FORMAT,version=1,events=[event('Export','error','failure','out.csv',values=list(range(30)))],dropped=0)
    compact=len(json.dumps(state,ensure_ascii=False).encode('utf-8'));pretty=len(json.dumps(state,ensure_ascii=False,indent=2).encode('utf-8'))
    assert pretty>compact
    monkeypatch.setattr(module,'MAX_STATE_BYTES',compact+1)
    path=tmp_path/'coverage-state.json';path.write_text('previous')
    with pytest.raises(ValueError):save_state(path,state)
    assert path.read_text()=='previous'
