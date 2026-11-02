import csv
import hashlib
from pathlib import Path
import pytest
from fireblade.core.ioc_hunt import parse_indicators,IndicatorMatcher,read_indicator_file
from fireblade.core.ioc_results import hunt,HuntStore,discover_hunts
from fireblade.core.workspace_reader import WorkspaceReader
from fireblade.core.engine import Case
from fireblade.core.models import AnalysisSnapshot,View
from fireblade.core.errors import OperationCancelled


def matches(iocs,text,sub=True):
    batch=parse_indicators(iocs)
    return {batch.indicators[i-1].value for i,_,_,_ in IndicatorMatcher(batch.indicators,sub).matches(text)}

@pytest.mark.parametrize('ioc,text,expected',[
 ('192.0.2.1','192.0.2.10',False),('192.0.2.1','x192.0.2.1',False),
 ('192.0.2.1','192[.]0[.]2[.]1',True),('2001:db8::1','[2001:0db8:0:0::1]',True),
 ('example.org','foo.example.org',True),('example.org','example.org.attacker.test',False),
 ('example.org','evil-example.org',False),('*.example.org','example.org',False),
 ('*.example.org','a.example.org',True),('faß.de','fass.de',False),('faß.de','xn--fa-hia.de',True),
 ('https://example.org/Case?A=B','https://EXAMPLE.org:443/Case?A=B',True),
 ('https://example.org/Case','https://example.org/case',False),
 ('a'*64,'A'*64,True),('a'*64,'a'*65,False),
])
def test_matching_boundaries(ioc,text,expected):assert bool(matches(ioc,text)) is expected


def test_parse_import(tmp_path):
    batch=parse_indicators('type,value,label\nip,192.0.2.1,first\nip,192.0.2.1,duplicate\ndomain,example.org,domain\nip,nope,bad\n')
    assert len(batch.indicators)==2 and batch.duplicates==1 and len(batch.rejected)==1
    path=tmp_path/'list.txt';path.write_text('# list\n192.0.2.1\nexample.org',encoding='utf-16')
    imported=read_indicator_file(path);assert len(imported.indicators)==2 and imported.origin['sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    assert not matches('example.org','a.example.org',False)


def make_documents(tmp_path):
    docs=[]
    for n in range(2):
        source=tmp_path/f'source{n}.csv'
        source.write_text('Timestamp,Address,Message\n2026-01-01,192.0.2.1,192.0.2.1 example.org\n2026-01-02,192.0.2.10,clean\n')
        case=Case(tmp_path/f'analysis{n}.timeline');case.import_csv(source)
        docs.append(AnalysisSnapshot(str(case.path),case.info,View(),b''));case.close()
    return docs


def test_complete_counts_cap_exports_persistence(tmp_path):
    docs=make_documents(tmp_path);before=[Path(d.source_info['path']).read_bytes() for d in docs]
    store=hunt(WorkspaceReader(docs),parse_indicators('192.0.2.1\nexample.org\nabsent.test'),tmp_path/'hunts',hit_limit=2)
    try:
        assert store.metadata['status']=='complete' and store.metadata['scanned_rows']==4
        assert store.metadata['matching_fields']==6 and store.metadata['truncated']
        rows=store.indicators();assert rows[0][5:7]==(4,2) and rows[1][5:7]==(2,2) and rows[2][5:7]==(0,0)
        assert store.page()['count']==2
        out=tmp_path/'summary.csv';store.export(out,summary=True)
        assert len(list(csv.reader(out.open(encoding='utf-8-sig'))))==4
        store.export(tmp_path/'hits.xlsx')
        assert before==[Path(d.source_info['path']).read_bytes() for d in docs]
        path=store.path
    finally:store.close()
    reopened=HuntStore(path);assert reopened.page()['count']==2;reopened.close()
    assert len(discover_hunts(tmp_path/'hunts')[0])==1


def test_filters_partial_and_cancel_cleanup(tmp_path):
    docs=make_documents(tmp_path);docs[0].view=View(search='clean')
    docs[1].path=str(tmp_path/'missing.timeline')
    store=hunt(WorkspaceReader(docs),parse_indicators('192.0.2.1'),tmp_path/'hunts',respect_filters=True)
    assert store.metadata['status']=='partial' and store.metadata['matching_fields']==0
    assert store.sources()[0]['scanned']==1 and store.sources()[1]['error'];store.close()
    reader=WorkspaceReader(docs);reader.interrupt()
    with pytest.raises(OperationCancelled):hunt(reader,parse_indicators('192.0.2.1'),tmp_path/'hunts')
    assert len(list((tmp_path/'hunts').iterdir()))==1


def test_cancel_during_scan_keeps_previous_hunt_and_export(tmp_path):
    import threading
    from fireblade.core.errors import cancellation_scope
    docs=make_documents(tmp_path);root=tmp_path/'hunts';batch=parse_indicators('192.0.2.1')
    previous=hunt(WorkspaceReader(docs),batch,root);path=previous.path
    reader=WorkspaceReader(docs)
    with pytest.raises(OperationCancelled):hunt(reader,batch,root,progress=lambda _:reader.interrupt())
    assert path.is_file() and len(list(root.iterdir()))==1
    target=tmp_path/'previous.csv';target.write_text('previous')
    cancelled=threading.Event();cancelled.set()
    with cancellation_scope(cancelled),pytest.raises(OperationCancelled):previous.export(target)
    assert target.read_text()=='previous'
    with pytest.raises(ValueError):previous.export(docs[0].path)
    previous.close()
