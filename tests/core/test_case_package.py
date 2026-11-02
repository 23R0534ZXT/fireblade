import hashlib
import json
from pathlib import Path
import threading
import zipfile

import pytest

from fireblade.core.case_package import export_package, import_package
from fireblade.core.engine import Case
from fireblade.core.errors import OperationCancelled, cancellation_scope
from fireblade.core.investigations import InvestigationLibrary
from fireblade.core.models import AnalysisSnapshot, View
from fireblade.core.sessions import read_session, write_session


def prepared(tmp_path):
    source=tmp_path/'source.csv';source.write_text('Timestamp,User,ID\n2026-01-01T00:00:00Z,élève,0009007199254740993\n')
    case=Case(tmp_path/'analysis.timeline');info=case.import_csv(source);case.bookmark(1,'Note <exacte>')
    document=AnalysisSnapshot(str(case.path),info,View(search='élève'),b'header')
    library=InvestigationLibrary(tmp_path/'cases');data=library.create('Case portable','Contexte')
    data=library.save(data['id'],[document],0,[],None,data['revision'])
    return library,data,document,case,source


def test_verified_package_moves_sources_annotations_views_and_collection_references(tmp_path):
    library,data,document,case,source=prepared(tmp_path)
    collection=tmp_path/'collection';collection.mkdir()
    write_session(collection/'collection.fireblade-session',[document],0)
    (collection/'collection.json').write_text(json.dumps(dict(root=str(tmp_path/'evidence'),output=str(collection),documents=[document.path])))
    data=library.save(data['id'],[document],0,[dict(path=str(collection),name='Collecte')],str(collection),data['revision'])
    try:
        digest=hashlib.sha256(source.read_bytes()).digest()
        archive=tmp_path/'case.fireblade-case'
        result=export_package(library,data,[document],0,archive,include_sources=True,active_case=case)
        assert not result['missing_sources']
        assert hashlib.sha256(source.read_bytes()).digest()==digest
    finally:case.close()
    source.unlink();Path(document.path).unlink()
    target=InvestigationLibrary(tmp_path/'another location'/'cases')
    imported=import_package(target,archive)['case']
    snapshots,active=read_session(target.session_path(imported));assert active==0
    restored=Case(snapshots[0].path)
    try:
        assert restored.info==snapshots[0].source_info
        assert restored.bookmarks()=={1:'Note <exacte>'}
        assert snapshots[0].view.search=='élève' and snapshots[0].header_state==b'header'
        assert Path(restored.info['path']).read_text().endswith(',élève,0009007199254740993\n')
        assert restored.page(View())[0][-1]=='0009007199254740993'
        nested,_=read_session(Path(imported['active_collection'])/'collection.fireblade-session')
        assert nested[0].path==snapshots[0].path and nested[0].source_info==restored.info
    finally:restored.close()


def test_changed_source_refuses_export_and_keeps_previous_archive(tmp_path):
    library,data,document,case,source=prepared(tmp_path)
    archive=tmp_path/'case.fireblade-case';archive.write_bytes(b'previous valid archive')
    source.write_text('Timestamp,User,ID\nchanged,changed,2\n')
    try:
        with pytest.raises(ValueError,match='Empreinte'):export_package(library,data,[document],0,archive,include_sources=True,active_case=case)
        assert archive.read_bytes()==b'previous valid archive'
        assert not list(tmp_path.glob('*.partial'))
    finally:case.close()


def test_import_rejects_tampering_and_publishes_no_case(tmp_path):
    library,data,document,case,source=prepared(tmp_path);archive=tmp_path/'good.fireblade-case'
    try:export_package(library,data,[document],0,archive,active_case=case)
    finally:case.close()
    bad=tmp_path/'bad.fireblade-case'
    with zipfile.ZipFile(archive) as original,zipfile.ZipFile(bad,'w') as rewritten:
        for item in original.infolist():
            payload=original.read(item)
            if item.filename.endswith('.timeline'):payload=payload[:-1]+bytes([payload[-1]^1])
            rewritten.writestr(item,payload)
    target=InvestigationLibrary(tmp_path/'target')
    with pytest.raises(ValueError,match='SHA-256'):import_package(target,bad)
    assert target.list()==([],[])
    assert not list(target.root.glob('.import-*'))


@pytest.mark.parametrize('name',['../outside','/outside','C:/outside','a\\outside','NUL.csv','folder/file.','folder/a?b'])
def test_unsafe_archive_paths_are_rejected(tmp_path,name):
    archive=tmp_path/'unsafe.fireblade-case'
    with zipfile.ZipFile(archive,'w') as output:output.writestr(name,b'bad')
    with pytest.raises(ValueError):import_package(InvestigationLibrary(tmp_path/'cases'),archive)
    assert not (tmp_path/'outside').exists()


def test_cancellation_keeps_existing_archive_and_cleans_staging(tmp_path):
    library,data,document,case,source=prepared(tmp_path);archive=tmp_path/'case.fireblade-case';archive.write_bytes(b'previous')
    cancelled=threading.Event();cancelled.set()
    try:
        with cancellation_scope(cancelled),pytest.raises(OperationCancelled):
            export_package(library,data,[document],0,archive,active_case=case)
        assert archive.read_bytes()==b'previous'
        assert not list(tmp_path.glob('*.partial'))
    finally:case.close()


def test_relocation_preserves_source_values_headers_and_filter_literals(tmp_path):
    from fireblade.core.case_package import relocate
    original='/old/source.csv';replacement='/new/sources/0000.csv'
    value=dict(path=original,source=dict(path=original,headers=[original]),
               view=dict(search=original,filters=[dict(column=0,operator='eq',value=original)]),
               columns={'/old/analysis.timeline':2},sources=['/old/analysis.timeline'])
    result=relocate(value,{original:replacement,'/old/analysis.timeline':'/new/analysis.timeline'})
    assert result['path']==replacement and result['source']['path']==replacement
    assert result['source']['headers']==[original] and result['view']==value['view']
    assert result['columns']=={'/new/analysis.timeline':2} and result['sources']==['/new/analysis.timeline']


def test_import_size_budget_prevents_case_creation(tmp_path,monkeypatch):
    import fireblade.core.case_package as module
    library,data,document,case,source=prepared(tmp_path);archive=tmp_path/'case.fireblade-case'
    try:export_package(library,data,[document],0,archive,active_case=case)
    finally:case.close()
    target=InvestigationLibrary(tmp_path/'target');monkeypatch.setattr(module,'MAX_BYTES',1)
    with pytest.raises(ValueError,match='64 Gio'):import_package(target,archive)
    assert target.list()==([],[]) and not list(target.root.glob('.import-*'))


def test_ioc_hunts_survive_portable_case_without_rewriting_observations(tmp_path):
    from fireblade.core.ioc_hunt import parse_indicators
    from fireblade.core.ioc_results import hunt,HuntStore,discover_hunts
    from fireblade.core.workspace_reader import WorkspaceReader
    library,data,document,case,source=prepared(tmp_path)
    source.write_text(source.read_text()+'2026-01-02,example.org,2\n')
    case.close();case=Case(tmp_path/'ioc-analysis.timeline');case.import_csv(source)
    document=AnalysisSnapshot(str(case.path),case.info,View(),b'')
    store=hunt(WorkspaceReader([document],active=case),parse_indicators('example.org'),library.folder(data['id'])/'IOC-hunts')
    original=store.page()['rows'][0][6:10];store.close()
    archive=tmp_path/'case.fireblade-case'
    try:export_package(library,data,[document],0,archive,include_sources=True,active_case=case)
    finally:case.close()
    target=InvestigationLibrary(tmp_path/'restored');result=import_package(target,archive)
    runs,errors=discover_hunts(target.folder(result['case']['id'])/'IOC-hunts');assert len(runs)==1 and not errors
    restored=HuntStore(runs[0]['path'])
    try:
        assert restored.page()['rows'][0][6:10]==original
        assert Path(restored.sources()[0]['path']).is_file()
        assert restored.sources()[0]['path']!=document.path
        assert Path(restored.sources()[0]['info']['path']).is_file()
    finally:restored.close()


def test_coverage_history_and_last_audit_are_transported_with_references(tmp_path):
    from fireblade.core.coverage import audit,event,save_state,load_state,save_report,load_report,FORMAT
    from fireblade.core.workspace_reader import WorkspaceReader
    library,data,document,case,source=prepared(tmp_path)
    folder=library.folder(data['id'])
    save_state(folder/'coverage-state.json',dict(format=FORMAT,version=1,events=[event('Import','info','Original '+str(source),document.path,source=str(source))],dropped=0))
    report=audit(WorkspaceReader([document],active=case));save_report(folder/'coverage-last.json',report)
    archive=tmp_path/'case.fireblade-case'
    try:export_package(library,data,[document],0,archive,include_sources=True,active_case=case)
    finally:case.close()
    target=InvestigationLibrary(tmp_path/'new-cases');result=import_package(target,archive);restored=target.folder(result['case']['id'])
    state=load_state(restored/'coverage-state.json');last=load_report(restored/'coverage-last.json')
    assert state['events'][0]['reason']=='Original '+str(source)
    assert Path(state['events'][0]['path']).is_file() and state['events'][0]['path']!=document.path
    assert Path(last['sources'][0]['path']).is_file() and last['stale']
