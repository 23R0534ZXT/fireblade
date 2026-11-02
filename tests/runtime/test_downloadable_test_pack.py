import hashlib
import io
import json
from pathlib import Path
import zipfile

import pytest

from scripts.test_pack.package import ARCHIVE,ROOT,package,verify_archive


@pytest.fixture
def demonstration_pack(tmp_path,monkeypatch):
    project=tmp_path/'project';(project/'config').mkdir(parents=True);(project/'LICENSE').write_text('MIT license')
    downloads={};fixtures=[]
    for name in ['SYSTEM','SYSTEM.LOG1','SYSTEM.LOG2']:
        url='https://example.invalid/'+name;data=('public fixture '+name).encode();downloads[url]=data
        fixtures.append(dict(tool='RECmd',name=name,url=url,compression=None,sha256=hashlib.sha256(data).hexdigest()))
    (project/'config/forensic-qa-fixtures.json').write_text(json.dumps(fixtures))
    (project/'config/forensic-browser-qa-fixtures.json').write_text('[]')
    downloads['https://example.invalid/evtx']=b'EVTX demonstration'
    notice=b'public license notice'
    lock=dict(evtx_fixture=dict(url='https://example.invalid/evtx',sha256=hashlib.sha256(downloads['https://example.invalid/evtx']).hexdigest()),registry_fixture_license=dict(url='https://example.invalid/license',sha256=hashlib.sha256(notice).hexdigest()))
    (project/'config/forensic-toolchain.json').write_text(json.dumps(lock))
    def fetch(url,expected=None):
        data=downloads.get(url,notice)
        if expected:assert hashlib.sha256(data).hexdigest()==expected
        return data
    monkeypatch.setattr('scripts.test_pack.package.fetch',fetch)
    output=tmp_path/'out';publication=package(output,project,volume_rows=12,source_commit='test-generator')
    return output,publication


def test_pack_retains_integrity_guide_provenance_and_adjacent_registry_logs(demonstration_pack):
    output,publication=demonstration_pack;manifest=verify_archive(output/ARCHIVE)
    assert publication['status']=='verified' and manifest['generator_commit']=='test-generator'
    paths={item['path'] for item in manifest['files']}
    for name in ['SYSTEM','SYSTEM.LOG1','SYSTEM.LOG2']:assert '01-Windows/01-Collecte-principale/RECmd/'+name in paths
    assert {'LIRE-MOI.md','RESULTATS-ATTENDUS.json','03-Exports/activite.csv','03-Exports/activite.tsv','03-Exports/activite.xlsx'}<=paths
    expected=manifest['expected'];assert len(expected['catscale']['families'])==7
    assert expected['catscale']['raw']==1 and expected['catscale']['rows']==26
    assert expected['volume_rows']==12
    with zipfile.ZipFile(output/ARCHIVE) as archive:
        assert b'synth' in archive.read(ROOT+'/LIRE-MOI.md')
        assert any(item['origin']['kind']=='public-artifact' for item in manifest['files'])
        assert not any(name.endswith(('.dll','.exe','.timeline')) for name in archive.namelist())


def test_modified_archive_cannot_pass_hash_verification(demonstration_pack,tmp_path):
    output,_=demonstration_pack;target=tmp_path/'modified.zip'
    with zipfile.ZipFile(output/ARCHIVE) as source,zipfile.ZipFile(target,'w') as outgoing:
        for name in source.namelist():outgoing.writestr(name,b'corrupt' if name.endswith('/activite.csv') else source.read(name))
    with pytest.raises(ValueError,match='size mismatch|SHA-256 mismatch'):verify_archive(target)


def test_extra_unsafe_entry_cannot_pass_verification(demonstration_pack,tmp_path):
    output,_=demonstration_pack;target=tmp_path/'extra.zip';target.write_bytes((output/ARCHIVE).read_bytes())
    with zipfile.ZipFile(target,'a') as archive:archive.writestr('../outside','not part of the verified pack')
    with pytest.raises(ValueError,match='Unexpected ZIP entries'):verify_archive(target)


def test_engine_extraction_rejects_an_unqualified_executable(tmp_path):
    from scripts.test_pack.validate_windows import extract_engines
    executable=tmp_path/'Fireblade.exe';executable.write_bytes(b'unqualified')
    with pytest.raises(ValueError,match='qualified Fireblade.exe'):extract_engines(executable,tmp_path/'engines')
