import json

import pytest

from fireblade.core.investigations import HISTORY_LIMIT, InvestigationLibrary
from fireblade.core.models import AnalysisSnapshot, View
from fireblade.core.sessions import read_session


def workspace(tmp_path):
    library=InvestigationLibrary(tmp_path/'cases');data=library.create('Récupération')
    path=tmp_path/'analysis.timeline';path.touch()
    return library,data,AnalysisSnapshot(str(path),{'path':str(tmp_path/'source.csv')},View(),b'header')


def test_history_is_bounded_and_restores_old_views_without_losing_current(tmp_path):
    library,data,document=workspace(tmp_path)
    for number in range(HISTORY_LIMIT+4):
        document.view.search=str(number)
        data=library.save(data['id'],[document],0,[],None,data['revision'])
    versions=library.history(data['id']);assert len(versions)==HISTORY_LIMIT
    oldest=versions[-1]
    restored=library.restore(data['id'],oldest['revision'],data['revision'])
    assert restored['revision']!=oldest['revision']
    assert read_session(library.session_path(restored))[0][0].view.search=='4'
    assert read_session(library.session_path(data))[0][0].view.search=='13'


def test_corrupt_manifest_is_listed_as_recoverable_and_can_be_restored(tmp_path):
    library,data,document=workspace(tmp_path)
    data=library.save(data['id'],[document],0,[],None,data['revision'])
    (library.folder(data['id'])/'case.json').write_text('{broken')
    records,errors=library.list()
    assert errors and records[0]['recovery_needed']
    restored=library.restore(data['id'],data['revision'])
    assert library.read(data['id'])==restored
    assert read_session(library.session_path(restored))[0]==[document]


def test_missing_analysis_does_not_replace_current_manifest_on_restore(tmp_path):
    library,data,document=workspace(tmp_path)
    data=library.save(data['id'],[document],0,[],None,data['revision'])
    before=(library.folder(data['id'])/'case.json').read_bytes()
    from pathlib import Path
    Path(document.path).unlink()
    with pytest.raises(ValueError,match='absente'):library.restore(data['id'],data['revision'],data['revision'])
    assert (library.folder(data['id'])/'case.json').read_bytes()==before


def test_stale_restore_is_rejected(tmp_path):
    library,data,document=workspace(tmp_path)
    data=library.save(data['id'],[document],0,[],None,data['revision'])
    library.update(data['id'],data['revision'],name='Autre modification')
    with pytest.raises(ValueError,match='modifié ailleurs'):library.restore(data['id'],data['revision'],data['revision'])


def test_symlink_case_does_not_break_catalogue_recovery(tmp_path):
    library,data,document=workspace(tmp_path)
    link=library.root/('0'*32)
    try:link.symlink_to(library.folder(data['id']),target_is_directory=True)
    except OSError:pytest.skip('Directory symlinks unavailable on this runner')
    records,errors=library.list()
    assert len(records)==1 and records[0]['id']==data['id'] and errors


def test_failed_history_cleanup_does_not_report_committed_save_as_failed(tmp_path,monkeypatch):
    library,data,document=workspace(tmp_path)
    def denied(*args):raise PermissionError('cleanup denied')
    monkeypatch.setattr(library,'prune_history',denied)
    saved=library.save(data['id'],[document],0,[],None,data['revision'])
    assert library.read(data['id'])==saved
    assert read_session(library.session_path(saved))[0]==[document]
