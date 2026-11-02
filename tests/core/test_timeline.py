import csv
import hashlib
from pathlib import Path
import threading

import pytest

from fireblade.core.engine import Case
from fireblade.core.errors import OperationCancelled
from fireblade.core.models import AnalysisSnapshot, Filter, View
from fireblade.core.timeline import TimelineStore, guess_time_column, utc_label
from fireblade.core.workspace_reader import WorkspaceReader


@pytest.fixture
def evidence(tmp_path):
    cases=[];documents=[]
    for n in range(2):
        source=tmp_path/f'source{n}.csv'
        with source.open('w',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['Timestamp','User','SourceIP','Path','SHA256','Description'])
            writer.writerows([
                ['2026-01-01T00:00:00.000000001Z','Alice','10.0.0.1','C:/same','abc','first'],
                ['2026-01-01T01:00:00.000000002+01:00','bob','10.0.0.1','D:/other','def','second'],
                ['2026-01-02 00:00:00','Alice','::1','C:/same','abc','naive'],
                ['broken','alicia','','C:/without','','undated'],
            ])
        case=Case(tmp_path/f'analysis{n}.timeline');case.import_csv(source);case.bookmark(1,'évidence');cases.append(case)
        documents.append(AnalysisSnapshot(str(case.path),case.info,View(),b''))
    store=TimelineStore(memory_mb=64)
    yield store,documents,cases
    store.close()
    for case in cases:case.close()


def build(store,documents,cases):
    # Inactive connections are closed, matching the application's ownership model.
    for case in cases[1:]:case.close()
    return store.build(WorkspaceReader(documents,active=cases[0]),{d.path:0 for d in documents})


def test_cross_artifact_nanosecond_order_timezone_and_missing_dates(evidence):
    store,documents,cases=evidence;sources=build(store,documents,cases)
    assert [(s['rows'],s['dated'],s['undated'],s['naive']) for s in sources]==[(4,3,1,1)]*2
    rows=store.page()['rows']
    assert [(r[0],r[1]) for r in rows[:4]]==[(0,1),(1,1),(0,2),(1,2)]
    assert rows[2][2]-rows[0][2]==1
    assert utc_label(rows[0][2])=='2026-01-01 00:00:00.000000001 UTC'
    assert store.parse_time('2026-01-01T00:00:00.000000001Z')==rows[0][2]
    start,end,count,dated=store.extent();hist=store.histogram(start,end)
    assert sum(row[2] for row in hist['rows'])==6
    assert count==8 and dated==6
    assert store.page(start=start,end=start)['count']==2
    assert store.page(start=start,end=start,include_undated=True)['count']==4


@pytest.mark.parametrize('kind,value,count',[('user','alice',4),('ip','10.0.0.1',4),('path','c:/same',4),('hash','abc',4)])
def test_typed_correlation_exact_matching_across_sources(evidence,kind,value,count):
    store,documents,cases=evidence;build(store,documents,cases)
    assert store.page(text=value,kind=kind,exact=True)['count']==count
    assert store.page(text=value,kind=kind,exact=True,sources=[1])['count']==count//2
    assert store.page(text="' OR 1=1 --",kind=kind,exact=True)['count']==0
    assert store.page(bookmarks=True)['count']==2


def test_cancelled_rebuild_preserves_previous_index(evidence):
    store,documents,cases=evidence;build(store,documents,cases)
    reader=WorkspaceReader(documents,active=cases[0]);reader.interrupt()
    with pytest.raises(OperationCancelled):store.build(reader,{d.path:0 for d in documents})
    assert store.page()['count']==8
    assert not (store.root/'bridge.csv').exists()


def test_missing_source_database_does_not_hide_other_sources(evidence,tmp_path):
    store,documents,cases=evidence
    documents.append(AnalysisSnapshot(str(tmp_path/'missing.timeline'),{'path':'missing.csv','headers':['Date']},View(),b''))
    sources=build(store,documents,cases)
    assert sources[-1]['error'] and store.page()['count']==8


def test_large_index_pagination_and_filters_use_whole_dataset(tmp_path):
    source=tmp_path/'source.csv'
    with source.open('w') as stream:
        stream.write('Timestamp,User,ID\n')
        for n in range(1800):stream.write(f'2026-01-01T00:00:00Z,user{n%3},{n:08}\n')
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    case=Case(tmp_path/'case.timeline');case.import_csv(source)
    doc=AnalysisSnapshot(str(case.path),case.info,View(filters=[Filter(1,'eq','user1')]),b'')
    store=TimelineStore(memory_mb=64)
    try:
        store.build(WorkspaceReader([doc],active=case),{doc.path:0})
        assert store.page(text='user1',kind='user',exact=True)['count']==600
        assert [row[1] for row in store.page(offset=1750)['rows']]==list(range(1751,1801))
        store.build(WorkspaceReader([doc],active=case),{doc.path:0},respect_filters=True)
        assert store.page()['count']==600
        assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    finally:store.close();case.close()


def test_dates_outside_int64_ns_range_still_filter_to_exact_nanosecond(tmp_path):
    source=tmp_path/'historical.csv'
    source.write_text('Timestamp,User\n1601-01-01T00:00:00.000000001Z,a\n1601-01-01T00:00:00.000000002Z,b\n9999-01-01T00:00:00.000000001Z,c\n')
    case=Case(tmp_path/'historical.timeline');case.import_csv(source)
    doc=AnalysisSnapshot(str(case.path),case.info,View(),b'');store=TimelineStore()
    try:
        store.build(WorkspaceReader([doc],active=case),{doc.path:0})
        for row in store.page()['rows']:
            assert store.page(start=row[2],end=row[2])['rows']==[row]
            assert sum(item[2] for item in store.histogram(row[2],row[2])['rows'])==1
    finally:store.close();case.close()


def test_cancellation_after_inserted_batch_rolls_back_and_cleans_chunks(evidence):
    store,documents,cases=evidence;build(store,documents,cases)
    reader=WorkspaceReader(documents,active=cases[0]);seen=[]
    def progress(message):
        if 'événements indexés' in message:seen.append(message);reader.interrupt()
    with pytest.raises(OperationCancelled):store.build(reader,{d.path:0 for d in documents},progress=progress)
    assert seen and store.page()['count']==8
    assert not list(store.root.glob('.fireblade-import-*'))
