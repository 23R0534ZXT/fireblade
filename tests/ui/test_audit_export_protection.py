import os
import time
import zipfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog

from fireblade.core.collection import Collection, ToolPack
from fireblade.core.engine import Case
from fireblade.ui.app import Window


def settle(app, window):
    deadline = time.monotonic()+15
    while time.monotonic() < deadline:
        app.processEvents()
        if not window.jobs and not window.pool.activeThreadCount() and (not window.model or not window.model.jobs):return
        time.sleep(.005)
    raise AssertionError('Export did not settle')


@pytest.fixture
def workspace(qt_application, tmp_path):
    window = Window(investigation_root=tmp_path/'cases'); errors = []
    window.error = lambda value: errors.append(str(value))
    source = tmp_path/'source.csv'; source.write_text('Value\none\ntwo\n')
    assert window.create_investigation('Export protection')
    case = Case(tmp_path/'analysis.timeline')
    try:case.import_csv(source)
    finally:case.close()
    window.load_case(tmp_path/'analysis.timeline'); settle(qt_application,window)
    assert window.save_investigation() and not errors
    yield window,errors
    settle(qt_application,window);assert window.close()


def write_export(window, writer, target, monkeypatch):
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(target),''))
    if writer == 'csv':window.export_csv()
    elif writer == 'session':window.save_session(target)
    elif writer == 'tle_session':window.export_tle_session(target)
    else:window.export_global_rules(target)


@pytest.mark.parametrize('writer',['csv','session','tle_session','global_rules'])
@pytest.mark.parametrize('destination',['case','coverage','timeline','global_rules'])
def test_every_export_preserves_internal_case_files(workspace,qt_application,writer,destination,monkeypatch):
    window,errors = workspace
    folder = window.investigation_library.folder(window.active_investigation['id'])
    window.rule_store.save(window.rule_book)
    target = {'case':folder/'case.json','coverage':folder/'coverage-state.json',
              'timeline':folder/'timeline-state.json','global_rules':window.rule_store.path}[destination]
    if not target.exists():target.write_text('{"marker":"must survive"}')
    before = target.read_bytes()
    write_export(window,writer,target,monkeypatch);settle(qt_application,window)
    assert target.read_bytes() == before and errors


@pytest.mark.parametrize('writer',['csv','session','tle_session','global_rules'])
def test_exports_still_write_new_external_files(workspace,qt_application,tmp_path,writer,monkeypatch):
    window,errors = workspace; target=tmp_path/(writer+'.csv' if writer=='csv' else writer+'.json')
    write_export(window,writer,target,monkeypatch);settle(qt_application,window)
    assert target.is_file() and not errors


@pytest.mark.parametrize('alias',[False,True])
@pytest.mark.parametrize('inactive',[False,True])
def test_raw_archive_and_hardlink_protected_for_active_and_saved_collection(workspace,qt_application,tmp_path,monkeypatch,alias,inactive):
    window,errors = workspace
    root=tmp_path/'evidence';root.mkdir();raw=root/'var-log.zip'
    with zipfile.ZipFile(raw,'w') as output:
        output.writestr('var/log/auth.log','2026-11-01T12:00:00Z host sshd[1]: Accepted password for alice from 192.0.2.1 port 22 ssh2\n')
    before=raw.read_bytes()
    collection=Collection(root,tmp_path/'work',ToolPack(tmp_path/'unused'));report=collection.parse()
    window.collection=collection
    window.load_case(report['documents'][0]['path']);settle(qt_application,window)
    window.investigation_collections=[dict(path=str(collection.output),name='Raw archive')]
    if inactive:window.collection=None
    target=raw
    if alias:
        target=tmp_path/'raw-alias.csv'
        try:os.link(raw,target)
        except OSError as exc:pytest.skip(str(exc))
    write_export(window,'csv',target,monkeypatch);settle(qt_application,window)
    assert raw.read_bytes() == before and errors
    assert target.read_bytes() == before


def test_metadata_hardlink_alias_is_protected(workspace,tmp_path):
    window,errors=workspace
    original=window.investigation_library.folder(window.active_investigation['id'])/'case.json'
    alias=tmp_path/'metadata-alias.json'
    try:os.link(original,alias)
    except OSError as exc:pytest.skip(str(exc))
    before=original.read_bytes();window.export_global_rules(alias)
    assert original.read_bytes()==before and errors


def test_hayabusa_sources_cannot_replace_analysis_source(workspace,tmp_path,monkeypatch):
    window,errors=workspace
    archive=tmp_path/'Hayabusa-source.zip'
    with zipfile.ZipFile(archive,'w') as output:output.writestr('source.txt','public sources')
    source=Path(window.case.info['path']);before=source.read_bytes()
    monkeypatch.setattr('fireblade.ui.collection.resource_path',lambda _:archive)
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(source),''))
    window.export_hayabusa_source()
    assert source.read_bytes()==before and errors


def test_hayabusa_failed_copy_preserves_target_and_cleans_temporary(workspace,tmp_path,monkeypatch):
    window,errors=workspace
    archive=tmp_path/'Hayabusa-source.zip';archive.write_bytes(b'ZIP placeholder')
    target=tmp_path/'export.zip';target.write_bytes(b'previous valid export')
    monkeypatch.setattr('fireblade.ui.collection.resource_path',lambda _:archive)
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(target),''))
    def fail(source,destination):
        Path(destination).write_bytes(b'partial');raise OSError('Copy interrupted')
    monkeypatch.setattr('shutil.copyfile',fail)
    window.export_hayabusa_source()
    assert target.read_bytes()==b'previous valid export' and errors
    assert not list(tmp_path.glob('*.partial'))
