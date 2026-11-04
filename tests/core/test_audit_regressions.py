"""Evidence-driven regressions from the 0.2.0 audit (FB020-01 to FB020-08)."""
import base64
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import zipfile

import duckdb
import pytest

from fireblade.core.case_package import import_package
from fireblade.core.collection import Collection, ToolPack
from fireblade.core.disk import DiskCollection
from fireblade.core.engine import Case
from fireblade.core.investigations import InvestigationLibrary
from fireblade.core.models import View


def test_actual_ntfs_image_traverses_and_copies_mft(tmp_path):
    fixture = Path(__file__).parents[1]/'fixtures/disks/ntfs.bin.gz'
    image = tmp_path/'ntfs.raw'; image.write_bytes(gzip.decompress(fixture.read_bytes()))
    original = hashlib.sha256(image.read_bytes()).hexdigest()
    collection = DiskCollection(image, tmp_path/'work', ToolPack(tmp_path/'unused'), source_kind='image')
    report = collection.parse()
    assert report['status'] == 'complete'
    assert report['disk']['visited'] > 10
    assert not report['disk']['errors']
    assert any(Path(item['extracted']).name == '$MFT' for item in report['disk']['artifacts'])
    assert hashlib.sha256(image.read_bytes()).hexdigest() == original


def test_sqlite_committed_wal_rows_survive_disk_extraction(tmp_path):
    root = tmp_path/'volume'; root.mkdir(); source = root/'History'
    producer = sqlite3.connect(source)
    try:
        producer.execute('PRAGMA journal_mode=WAL')
        producer.execute('CREATE TABLE visits(url TEXT)'); producer.commit()
        producer.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        producer.execute("INSERT INTO visits VALUES ('https://evidence.example/committed')"); producer.commit()
        originals = {p.name: p.read_bytes() for p in root.iterdir()}
        collection = DiskCollection(root, tmp_path/'work', ToolPack(tmp_path/'unused'))
        list(collection.walk_sources(lambda error: pytest.fail(str(error))))
        copied = collection.root/'volume/History'
        assert {p.name for p in copied.parent.iterdir()} == set(originals)
        with sqlite3.connect(f'file:{copied}?mode=ro', uri=True) as restored:
            assert restored.execute('SELECT url FROM visits').fetchall() == [('https://evidence.example/committed',)]
        assert all((root/name).read_bytes() == value for name,value in originals.items())
    finally: producer.close()


def test_changing_sqlite_companion_discards_entire_extraction_group(tmp_path, monkeypatch):
    source = tmp_path/'volume'; source.mkdir()
    main = source/'History'; main.write_bytes(b'SQLite format 3\0'+b'0'*100)
    wal = source/'History-wal'; wal.write_bytes(b'original journal')
    collection = DiskCollection(source, tmp_path/'work', ToolPack(tmp_path/'unused'))
    copy = collection.copy_artifact
    def mutate(*args):
        result = copy(*args)
        if args[0] == wal:wal.write_bytes(b'changed journal')
        return result
    monkeypatch.setattr(collection, 'copy_artifact', mutate)
    list(collection.walk_sources(lambda _: None))
    assert not collection.disk['artifacts'] and collection.disk['extracted'] == 0
    assert collection.disk['errors'] and not list(collection.root.rglob('History*'))


def malicious_database(root, variant):
    source = root/'source.csv'; source.write_text('Value\noriginal\n')
    path = root/'attack.timeline'; case = Case(path)
    try: info = case.import_csv(source)
    finally: case.close()
    marker = root/'outside.txt'; marker.write_text('SYNTHETIC PRIVATE MARKER')
    quoted = str(marker).replace("'", "''")
    db = duckdb.connect(str(path))
    try:
        if variant == 'metadata':
            db.execute('DROP TABLE metadata')
            db.execute(f"CREATE VIEW metadata AS SELECT 'source' AS key,content AS value FROM read_text('{quoted}')")
        else:
            db.execute('DROP TABLE events')
            db.execute(f"CREATE VIEW events AS SELECT 1::BIGINT AS __row_id,content AS c0 FROM read_text('{quoted}')")
    finally: db.close()
    return path, info


@pytest.mark.parametrize('variant', ['events','metadata'])
def test_untrusted_timeline_schema_is_rejected_on_direct_open(tmp_path, variant):
    path, _ = malicious_database(tmp_path, variant)
    with pytest.raises((ValueError, duckdb.Error)): Case(path)
    # Failed validation releases its database handle, including on Windows.
    path.unlink()


def test_hash_valid_portable_package_rejects_executable_sql_view(tmp_path):
    path, info = malicious_database(tmp_path, 'events')
    library = InvestigationLibrary(tmp_path/'original'); original = library.create('Untrusted')
    member = 'analyses/0000.timeline'
    payload = path.read_bytes()
    manifest = dict(format='fireblade-case-package', version=1, case=original,
        documents=[dict(database=member, source=info, view=json.loads(View().to_json()), header=base64.b64encode(b'').decode())],
        active=0, files=[dict(path=member, size=len(payload), sha256=hashlib.sha256(payload).hexdigest())],
        collections=[], relocation={str(path):member}, missing_sources=[info['path']])
    archive = tmp_path/'attack.fireblade-case'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr(member,payload); output.writestr('manifest.json',json.dumps(manifest))
    target = InvestigationLibrary(tmp_path/'target')
    with pytest.raises((ValueError, duckdb.Error)): import_package(target, archive)
    assert target.list() == ([], []) and not list(target.root.glob('.import-*'))


def test_existing_analysis_cannot_read_other_local_files(tmp_path):
    source = tmp_path/'source.csv'; source.write_text('Value\none\n')
    case = Case(tmp_path/'analysis.timeline')
    try:
        case.import_csv(source)
        with pytest.raises(duckdb.PermissionException):
            case.db.execute('SELECT * FROM read_text(?)', [str(source)])
        assert case.page(View()) == [(1,'one')]
    finally: case.close()


def test_external_access_cannot_escape_through_spill_symlinks(tmp_path):
    source=tmp_path/'source.csv';source.write_text('Value\noriginal\n')
    case=Case(tmp_path/'analysis.timeline')
    try:
        case.import_csv(source)
        spill=Path(str(case.path)+'.tmp');spill.mkdir(exist_ok=True)
        alias=spill/'alias.txt'
        try:alias.symlink_to(source)
        except OSError as exc:pytest.skip(str(exc))
        with pytest.raises(duckdb.PermissionException):case.db.execute('SELECT * FROM read_text(?)',[str(alias)])
    finally:case.close()


def test_fake_derived_view_does_not_grant_access_to_local_files(tmp_path):
    source=tmp_path/'source.csv';source.write_text('Value\noriginal\n')
    path=tmp_path/'analysis.timeline';case=Case(path)
    try:
        case.import_csv(source)
        case.add_derived_columns([dict(name='Extra',operation='expression',expression='[Value]')])
    finally:case.close()
    quoted=str(source).replace("'","''")
    db=duckdb.connect(str(path))
    try:
        db.execute('DROP VIEW events')
        db.execute(f"CREATE VIEW events AS SELECT a.*,t.content AS c1 FROM __fireblade_source_events a CROSS JOIN read_text('{quoted}') t")
    finally:db.close()
    try:case=Case(path)
    except (ValueError,duckdb.Error):return
    try:
        with pytest.raises(duckdb.PermissionException):case.page(View())
    finally:case.close()


def test_changed_collection_source_never_enters_saved_session(tmp_path, monkeypatch):
    root = tmp_path/'source'; root.mkdir(); source = root/'events.csv'
    source.write_text('Value\noriginal\n')
    collection = Collection(root, tmp_path/'work', ToolPack(tmp_path/'unused'))
    original = collection.import_result
    def mutate(*args, **kwargs):
        result = original(*args, **kwargs); source.write_text('Value\nchanged\n'); return result
    monkeypatch.setattr(collection,'import_result',mutate)
    report = collection.parse()
    assert report['files'][0]['status'] == 'error'
    assert not report['documents']
    assert not (collection.output/'collection.fireblade-session').exists()


def test_overlong_unicode_domain_rejected_before_idna_processing(monkeypatch):
    import fireblade.core.ioc_hunt as module
    calls = []
    monkeypatch.setattr(module.idna,'encode',lambda *args,**kwargs: calls.append(args) or b'invalid')
    with pytest.raises(ValueError):module.normalize_domain('\u0660'*1000+'.example')
    assert calls == []
