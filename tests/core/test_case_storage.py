from pathlib import Path
import pytest
from fireblade.core.case_storage import archive_and_release, restore_archive
from fireblade.core.case_package import verify_package
from fireblade.core.investigations import InvestigationLibrary
from fireblade.core.engine import Case
from fireblade.core.models import AnalysisSnapshot,View
from fireblade.core.sessions import read_session


def prepared(tmp_path):
    library=InvestigationLibrary(tmp_path/'cases');data=library.create('Storage')
    folder=library.folder(data['id']);source=tmp_path/'original.csv';source.write_text('ID\n001\n')
    case=Case(folder/'analysis.timeline');case.import_csv(source);case.bookmark(1,'Keep this note')
    doc=AnalysisSnapshot(str(case.path),case.info,View(),b'');case.close()
    data=library.save(data['id'],[doc],0,[],None,data['revision'])
    (folder/'manual-notes.txt').write_text('Manual evidence notes')
    return library,data,source


def test_verified_archive_releases_files_and_restores_notes(tmp_path):
    library,data,source=prepared(tmp_path);original=source.read_bytes();folder=library.folder(data['id'])
    archive=tmp_path/'storage.fireblade-case'
    result=archive_and_release(library,data['id'],archive)
    assert result['removed_bytes']>0 and source.read_bytes()==original
    assert not (folder/'analysis.timeline').exists()
    assert library.read(data['id'])['storage_archive']['path']==str(archive)
    verify_package(archive)
    restored=restore_archive(library,data['id'])['case']
    docs,_=read_session(library.session_path(restored))
    case=Case(docs[0].path)
    try:assert case.bookmarks()=={1:'Keep this note'} and case.page(View())==[(1,'001')]
    finally:case.close()
    assert (library.folder(restored['id'])/'case-extra/manual-notes.txt').read_text()=='Manual evidence notes'


def test_failed_archive_never_removes_local_work(tmp_path,monkeypatch):
    library,data,_=prepared(tmp_path);folder=library.folder(data['id'])
    def fail(*a,**k):raise OSError('Disk full')
    monkeypatch.setattr('fireblade.core.case_storage.export_package',fail)
    with pytest.raises(OSError):archive_and_release(library,data['id'],tmp_path/'backup.fireblade-case')
    assert (folder/'analysis.timeline').is_file() and (folder/'manual-notes.txt').is_file()
    assert not library.read(data['id']).get('storage_archive')


def test_archive_cannot_be_saved_inside_removed_case(tmp_path):
    library,data,_=prepared(tmp_path)
    with pytest.raises(ValueError):archive_and_release(library,data['id'],library.folder(data['id'])/'backup.fireblade-case')
