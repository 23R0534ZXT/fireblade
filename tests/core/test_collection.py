import json
from pathlib import Path
import sys
import threading
import time

import pytest

from fireblade.core.collection import Collection, ToolPack, execute, identify, sha256
from fireblade.core.engine import Case
from fireblade.core.errors import OperationCancelled, cancellation_scope
from fireblade.core.models import View
from fireblade.ui.workspace import read_session


@pytest.fixture
def collection(tmp_path):
    root = tmp_path/'evidence';root.mkdir()
    (root/'Security.evtx').write_bytes(b'ElfFile\0'+b'\0'*48)
    (root/'notes.txt').write_text('unsupported')
    (root/'data.csv').write_text('User,Value\nalice,001\n')
    pack = tmp_path/'pack'
    (pack/'EvtxECmd').mkdir(parents=True)
    (pack/'EvtxECmd'/'EvtxECmd.dll').touch()
    (pack/'dotnet').mkdir();(pack/'dotnet'/'dotnet.exe').touch()
    (pack/'Hayabusa'/'rules').mkdir(parents=True)
    (pack/'Hayabusa'/'hayabusa.exe').touch()
    return Collection(root, tmp_path/'work', ToolPack(pack))


def fake_execute(command, cwd, log, timeout=3600):
    Path(log).write_text('tool executed')
    if '--csv' in command:
        target = Path(command[command.index('--csv')+1])/'events.csv'
        target.write_text('EventID,Computer,RecordID\n4624,PC01,12\n')
    else:
        target = Path(command[command.index('-o')+1])
        source = next(Path(command[command.index('-d')+1]).glob('*.evtx'))
        target.write_text('Level,RuleTitle,RecordID,EvtxFile\nhigh,Test detection,12,'+str(source)+'\n')


def test_collect_parse_session_and_alerts(collection, monkeypatch):
    monkeypatch.setattr('fireblade.core.collection.execute', fake_execute)
    before = sha256(collection.root/'Security.evtx')
    report = collection.parse()
    assert report['status'] == 'complete'
    assert sorted(e['status'] for e in report['files']) == ['complete', 'complete', 'unsupported']
    snapshots, _ = read_session(collection.output/'collection.fireblade-session')
    assert len(snapshots)==2
    assert sha256(collection.root/'Security.evtx')==before
    report = collection.analyze()
    assert report['detection']['status']=='complete'
    case = Case(report['detection']['analysis'])
    try:
        assert case.count(View())==1
        assert case.headers[-1]=='Fireblade_EVTX_Source'
        assert case.page(View())[0][-1]==str(collection.root/'Security.evtx')
    finally:case.close()
    assert len(read_session(collection.output/'collection.fireblade-session')[0])==3
    restored = Collection.reopen(collection.output, collection.pack)
    assert restored.report==json.loads((collection.output/'collection.json').read_text())


def test_missing_parser_is_reported_without_losing_native_results(collection):
    (Path(collection.pack.root)/'EvtxECmd'/'EvtxECmd.dll').unlink()
    report = collection.parse()
    event = next(e for e in report['files'] if 'EvtxECmd' in e.get('tools', []))
    assert event['status']=='attention'
    assert event['runs'][0]['status']=='error'
    assert len(report['documents'])==1


def test_changed_evidence_blocks_detection(collection, monkeypatch):
    monkeypatch.setattr('fireblade.core.collection.execute', fake_execute)
    collection.parse()
    (collection.root/'Security.evtx').write_bytes(b'changed')
    report = collection.analyze()
    assert report['detection']['status']=='error'
    assert 'modifié' in report['detection']['error']
    assert not report['detection']['outputs']


def test_no_csv_is_not_silently_treated_as_parsed(collection, monkeypatch):
    monkeypatch.setattr('fireblade.core.collection.execute', lambda *a,**k: None)
    report=collection.parse()
    assert any(r['status']=='no_output' for e in report['files'] for r in e.get('runs', []))


def test_output_inside_evidence_and_existing_outputs_are_refused(collection):
    with pytest.raises(ValueError):Collection(collection.root, collection.root/'results', collection.pack)
    collection.output.mkdir()
    with pytest.raises(FileExistsError):collection.parse()


def test_cancel_kills_running_engine_tree(tmp_path):
    event=threading.Event()
    timer=threading.Timer(.3,event.set);timer.start()
    started=time.monotonic()
    try:
        with cancellation_scope(event), pytest.raises(OperationCancelled):
            execute([sys.executable,'-c','import time; time.sleep(30)'],tmp_path,tmp_path/'process.log')
    finally:timer.cancel()
    assert time.monotonic()-started<10


def test_inventory_preserves_unknown_and_unfollowed_symlinks(collection, monkeypatch):
    try:(collection.root/'loop').symlink_to(collection.root,target_is_directory=True)
    except OSError:pytest.skip('Symlinks unavailable')
    monkeypatch.setattr('fireblade.core.collection.execute', fake_execute)
    report=collection.parse()
    assert any(e['status']=='skipped' and Path(e['path']).name=='loop' for e in report['files'])


def test_registry_and_sqlite_dispatch(tmp_path):
    system=tmp_path/'SYSTEM';system.write_bytes(b'regf'+b'\0'*32)
    assert identify(system)==['AppCompatCacheParser','RECmd']
    amcache=tmp_path/'Amcache.hve';amcache.write_bytes(b'regf')
    assert identify(amcache)==['AmcacheParser']
    browser=tmp_path/'History';browser.write_bytes(b'SQLite format 3\0')
    assert identify(browser)==['SQLECmd']


def test_empty_hayabusa_output_requires_explicit_zero_summary(collection, monkeypatch):
    monkeypatch.setattr('fireblade.core.collection.execute', fake_execute)
    collection.parse()
    def empty(command, cwd, log, timeout=3600):
        Path(command[command.index('-o')+1]).touch()
        Path(log).write_text('Total | Unique detections: 0 | 0\n')
    monkeypatch.setattr('fireblade.core.collection.execute', empty)
    report = collection.analyze()
    assert report['detection']['status']=='complete'
    assert report['detection']['alerts']==0
    case=Case(report['detection']['analysis'])
    try:assert case.count(View())==0
    finally:case.close()
    def ambiguous(command, cwd, log, timeout=3600):
        Path(command[command.index('-o')+1]).touch()
        Path(log).write_text('No completion summary')
    monkeypatch.setattr('fireblade.core.collection.execute', ambiguous)
    assert collection.analyze()['detection']['status']=='error'


def test_hayabusa_unmapped_evidence_is_rejected(collection, monkeypatch):
    monkeypatch.setattr('fireblade.core.collection.execute', fake_execute)
    collection.parse()
    def unrelated(command, cwd, log, timeout=3600):
        fake_execute(command,cwd,log,timeout)
        Path(command[command.index('-o')+1]).write_text('Level,EvtxFile\nhigh,unknown.evtx\n')
    monkeypatch.setattr('fireblade.core.collection.execute', unrelated)
    report=collection.analyze()
    assert report['detection']['status']=='error'
    assert 'non reconnue' in report['detection']['error']


def test_registry_logs_are_companions_and_tampering_is_detected(collection, monkeypatch):
    system=collection.root/'SYSTEM';system.write_bytes(b'regf'+b'0'*40)
    log=collection.root/'SYSTEM.LOG1';log.write_bytes(b'regf'+b'1'*40)
    assert identify(log)==['companion']
    def mutate(command, cwd, destination, timeout=3600):
        fake_execute(command,cwd,destination,timeout)
        if 'SYSTEM' in command:
            log.write_bytes(b'modified')
        # -f uses an absolute source path.
        if any(str(system)==part for part in command):
            log.write_bytes(b'modified')
    monkeypatch.setattr('fireblade.core.collection.execute', mutate)
    monkeypatch.setattr(collection.pack, 'arguments', lambda tool,source,output: ['fake','-f',str(source),'--csv',str(output)])
    report=collection.parse()
    system_entry=next(e for e in report['files'] if e['path']==str(system))
    assert system_entry['status']=='error'
    assert 'transaction modifié' in system_entry['error']
    assert next(e for e in report['files'] if e['path']==str(log))['status']=='companion'


def test_cross_file_detection_keeps_all_original_evtx_references(collection, monkeypatch):
    (collection.root/'System.evtx').write_bytes(b'ElfFile\0'+b'1'*40)
    monkeypatch.setattr('fireblade.core.collection.execute', fake_execute)
    collection.parse()
    def correlated(command, cwd, log, timeout=3600):
        paths=sorted(Path(command[command.index('-d')+1]).glob('*.evtx'))
        Path(log).write_text('Success')
        Path(command[command.index('-o')+1]).write_text('Level,EvtxFile\nhigh,'+' ¦ '.join(str(p) for p in paths)+'\n')
    monkeypatch.setattr('fireblade.core.collection.execute', correlated)
    report=collection.analyze()
    assert report['detection']['status']=='complete'
    case=Case(report['detection']['analysis'])
    try:
        origins=json.loads(case.page(View())[0][-1])
        assert set(origins)=={str(collection.root/'Security.evtx'),str(collection.root/'System.evtx')}
    finally:case.close()


@pytest.mark.parametrize('mode',['artifacts','combined'])
def test_collection_organization_preserves_rows_fields_and_provenance(collection, monkeypatch, mode):
    (collection.root/'System.evtx').write_bytes(b'ElfFile\0'+b'1'*40)
    (collection.root/'other.csv').write_text('user,Artefact,Value\nbob,original,0002\n')
    collection.report['organization']=mode
    monkeypatch.setattr('fireblade.core.collection.execute', fake_execute)
    report=collection.parse()
    assert report['status']=='complete'
    snapshots,_=read_session(collection.output/'collection.fireblade-session')
    assert len(snapshots)==(1 if mode=='combined' else 2)
    assert len(report['raw_documents'])==4
    total=0
    records=[]
    for snapshot in snapshots:
        case=Case(snapshot.path)
        try:
            total+=case.count(View())
            assert snapshot.view.groups==([0] if mode=='combined' else [])
            for row in case.page(View()):records.append(dict(zip(case.headers,row[1:])))
            if mode=='combined':
                assert 'User' in case.headers
                assert any(h.startswith('user (') for h in case.headers)
                assert case.headers[0]!='Artefact'  # the original source's Artefact remains intact
        finally:case.close()
    assert total==4
    assert {row['Fichier source'] for row in records}=={str(collection.root/name) for name in ('data.csv','other.csv','Security.evtx','System.evtx')}
    assert any('0002' in row.values() and 'original' in row.values() for row in records)
    restored=Collection.reopen(collection.output,collection.pack)
    assert restored.report['organization']==mode
    if mode=='artifacts':
        assert {Path(s.source_info['path']).stem for s in snapshots}=={'EVTX','Exports CSV'}


def test_organization_failure_keeps_original_session(collection, monkeypatch):
    collection.report['organization']='combined'
    monkeypatch.setattr('fireblade.core.collection.execute',fake_execute)
    original=collection.import_result
    def fail_organized(source,kind,**kwargs):
        if kind=='organized':raise ValueError('Organisation interrompue')
        return original(source,kind,**kwargs)
    monkeypatch.setattr(collection,'import_result',fail_organized)
    with pytest.raises(ValueError,match='Organisation interrompue'):collection.parse()
    assert len(read_session(collection.output/'collection.fireblade-session')[0])==2
    assert collection.report['status']=='error'
