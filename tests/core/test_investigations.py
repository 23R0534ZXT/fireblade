import json
from pathlib import Path

import pytest

from fireblade.core.investigations import InvestigationLibrary
from fireblade.core.models import AnalysisSnapshot, View
from fireblade.core.sessions import read_session


def snapshot(tmp_path, name='analysis'):
    path=tmp_path/(name+'.timeline');path.write_bytes(b'file reference')
    return AnalysisSnapshot(str(path),{'path':str(tmp_path/(name+'.csv'))},View(),b'header')


def test_catalogue_is_durable_and_does_not_read_session_or_analysis(tmp_path):
    library=InvestigationLibrary(tmp_path/'cases')
    assert library.list()==([],[]) and not library.root.exists()
    data=library.create('Client A','Enquête réseau','windows')
    data=library.save(data['id'],[snapshot(tmp_path)],0,[],None,data['revision'])
    library.session_path(data).unlink()
    (tmp_path/'analysis.timeline').unlink()
    records,errors=InvestigationLibrary(library.root).list()
    assert not errors and records[0]['name']=='Client A' and records[0]['analysis_count']==1


def test_case_and_session_save_together_and_keep_previous_snapshot(tmp_path):
    library=InvestigationLibrary(tmp_path/'cases');data=library.create('Test')
    first=snapshot(tmp_path);first.view.search='alice'
    data=library.save(data['id'],[first],0,[],None,data['revision'])
    previous=library.session_path(data)
    restored,active=read_session(previous)
    assert active==0 and restored[0].view.search=='alice' and restored[0].header_state==b'header'
    first.view.search='bob'
    data=library.save(data['id'],[first],0,[],None,data['revision'])
    assert previous.exists() and read_session(library.session_path(data))[0][0].view.search=='bob'
    data=library.save(data['id'],[], -1,[],None,data['revision'])
    assert data['session'] is None and data['analysis_count']==0
    assert len(list(library.folder(data['id']).glob('session-*.fireblade-session')))<=1


def test_failed_manifest_commit_keeps_previous_session(tmp_path,monkeypatch):
    import fireblade.core.investigations as module
    library=InvestigationLibrary(tmp_path/'cases');data=library.create('Test')
    data=library.save(data['id'],[snapshot(tmp_path)],0,[],None,data['revision'])
    original=(library.folder(data['id'])/'case.json').read_bytes()
    def denied(*args):raise PermissionError('disque verrouillé')
    monkeypatch.setattr(module,'write_json',denied)
    with pytest.raises(PermissionError):library.save(data['id'],[], -1,[],None,data['revision'])
    assert (library.folder(data['id'])/'case.json').read_bytes()==original
    assert library.session_path(library.read(data['id'])).exists()


def test_stale_save_cannot_overwrite_another_case_revision(tmp_path):
    library=InvestigationLibrary(tmp_path/'cases');data=library.create('Before')
    updated=library.update(data['id'],data['revision'],name='After')
    with pytest.raises(ValueError,match='modifié ailleurs'):
        library.save(data['id'],[], -1,[],None,data['revision'])
    assert library.read(data['id'])==updated


def test_archive_edit_and_invalid_metadata_are_isolated(tmp_path):
    library=InvestigationLibrary(tmp_path/'cases');one=library.create('One');two=library.create('Two')
    library.update(one['id'],status='archived',description='Conserver')
    (library.folder(two['id'])/'case.json').write_text('{broken')
    records,errors=library.list()
    assert len(records)==len(errors)==1
    assert records[0]['status']=='archived' and records[0]['description']=='Conserver'


@pytest.mark.parametrize('identifier',['../outside','a/b','',None,'x'*32])
def test_case_identifier_never_escapes_library(tmp_path,identifier):
    with pytest.raises(ValueError):InvestigationLibrary(tmp_path).folder(identifier)


def test_oversized_session_and_invalid_selection_do_not_replace_manifest(tmp_path):
    library=InvestigationLibrary(tmp_path/'cases');data=library.create('Test')
    entry=snapshot(tmp_path);entry.source_info['padding']='x'*(4*1024*1024)
    with pytest.raises(ValueError,match='4 Mo'):library.save(data['id'],[entry],0,[],None,data['revision'])
    with pytest.raises(ValueError):library.save(data['id'],[entry],2,[],None,data['revision'])
    assert library.read(data['id'])==data
    assert not list(library.folder(data['id']).glob('*.fireblade-session'))
