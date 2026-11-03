import hashlib
import json
from pathlib import Path
import struct
import threading

import pytest

from fireblade.core.collection import ToolPack
from fireblade.core.disk import DiskCollection, candidate
from fireblade.core.engine import Case
from fireblade.core.errors import cancellation_scope


LOG = b'2026-11-03T12:00:00Z host sshd[42]: Accepted publickey for alice from 192.0.2.1 port 22 ssh2\n'


def fat_image(path):
    """Small real FAT12 filesystem with /VAR/LOG/AUTH.LOG, without external tools."""
    data = bytearray(1474560)
    data[:11] = b'\xeb\x3c\x90MSDOS5.0'
    struct.pack_into('<HBHBHHBHHHII', data, 11, 512, 1, 1, 2, 224, 2880, 0xf0, 9, 18, 2, 0, 0)
    data[36:62] = b'\x00\x00\x29\x12\x34\x56\x78FIREBLADE  FAT12   '
    data[510:512] = b'\x55\xaa'
    fat = bytearray(9*512); fat[:3] = b'\xf0\xff\xff'
    for cluster in (2, 3, 4):
        offset = cluster+cluster//2
        value = int.from_bytes(fat[offset:offset+2], 'little')
        value |= 0xfff << (4 if cluster % 2 else 0)
        fat[offset:offset+2] = value.to_bytes(2, 'little')
    data[512:512+len(fat)] = fat; data[5120:5120+len(fat)] = fat
    def entry(name, attr, cluster, size=0):
        record = bytearray(32); record[:11] = name; record[11] = attr
        struct.pack_into('<HHH', record, 22, 0, 0x5d63, cluster)
        struct.pack_into('<I', record, 28, size)
        return record
    data[19*512:19*512+32] = entry(b'VAR        ', 16, 2)
    data[33*512:33*512+32] = entry(b'LOG        ', 16, 3)
    data[34*512:34*512+32] = entry(b'AUTH    LOG', 32, 4, len(LOG))
    data[35*512:35*512+len(LOG)] = LOG
    path.write_bytes(data)
    return path


def test_mounted_results_are_closed_and_published_before_completion(tmp_path):
    root = tmp_path/'volume'; (root/'var/log').mkdir(parents=True)
    source = root/'var/log/auth.log'; source.write_bytes(LOG)
    (root/'other.txt').write_text('not an artifact')
    published = []
    collection = DiskCollection(root, tmp_path/'work', ToolPack(tmp_path/'tools'))
    def ready(documents):
        assert collection.report['status'] == 'running'
        for document in documents:
            case = Case(document['path'])
            try: assert case.info['rows'] > 0
            finally: case.close()
        published.extend(documents)
    collection.ready = ready
    report = collection.parse()
    assert report['status'] == 'complete'
    assert report['disk']['visited'] == 2
    assert report['disk']['extracted'] == 1
    assert published and published[0]['navigation']['relative'] == 'var/log/auth.log'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == report['disk']['artifacts'][0]['sha256']
    assert json.loads((tmp_path/'work/collection/disk-source.json').read_text())['source'] == str(root)


def test_raw_fat_image_is_read_without_modification(tmp_path):
    image = fat_image(tmp_path/'disk.img'); original = image.read_bytes()
    collection = DiskCollection(image, tmp_path/'work', ToolPack(tmp_path/'tools'), source_kind='image')
    report = collection.parse()
    assert report['status'] == 'complete'
    assert report['documents'], report
    assert report['disk']['artifacts'][0]['partition'] == 'partition-1'
    assert image.read_bytes() == original


def test_cancel_retains_completed_outputs(tmp_path):
    root = tmp_path/'volume'; (root/'var/log').mkdir(parents=True)
    (root/'var/log/auth.log').write_bytes(LOG)
    (root/'var/log/syslog').write_bytes(LOG)
    event = threading.Event()
    collection = DiskCollection(root, tmp_path/'work', ToolPack(tmp_path/'tools'), ready=lambda _: event.set())
    with cancellation_scope(event):
        report = collection.parse()
    assert report['status'] == 'cancelled'
    assert report['documents']
    assert (collection.output/'collection.fireblade-session').is_file()


def test_workspace_on_source_is_rejected(tmp_path):
    source = tmp_path/'volume'; source.mkdir()
    with pytest.raises(ValueError, match='hors du volume'):
        DiskCollection(source, source/'work', ToolPack(tmp_path/'tools'))
    assert not (source/'work').exists()


def test_bad_image_reports_failure(tmp_path):
    image = tmp_path/'bad.img'; image.write_bytes(b'not a disk')
    collection = DiskCollection(image, tmp_path/'work', ToolPack(tmp_path/'tools'), source_kind='image')
    with pytest.raises(Exception): collection.parse()
    assert collection.report['status'] == 'error'
    assert not collection.report['documents']


def test_complete_mbr_disk_exposes_both_partitions(tmp_path):
    volume = fat_image(tmp_path/'volume.img').read_bytes()
    first, second = 2048, 2048+2880
    disk = bytearray((second+2880)*512)
    disk[510:512] = b'\x55\xaa'
    for i, start in enumerate((first, second)):
        struct.pack_into('<B3sB3sII', disk, 446+i*16, 0, b'\0'*3, 1, b'\0'*3, start, 2880)
        disk[start*512:start*512+len(volume)] = volume
    image = tmp_path/'full-disk.raw'; image.write_bytes(disk)
    collection = DiskCollection(image, tmp_path/'work', ToolPack(tmp_path/'tools'), source_kind='image')
    report = collection.parse()
    assert report['status'] == 'complete'
    assert {a['partition'] for a in report['disk']['artifacts']} == {'partition-1', 'partition-2'}
    assert len(report['documents']) == 2


def test_physical_stream_pipeline_on_raw_fixture(tmp_path):
    import os
    if os.name == 'nt':
        pytest.skip('Windows device IOCTL requires an actual device')
    image = fat_image(tmp_path/'device.img')
    collection = DiskCollection(image, tmp_path/'work', ToolPack(tmp_path/'tools'), source_kind='physical')
    report = collection.parse()
    assert report['status'] == 'complete'
    assert report['documents']


def test_disk_case_package_keeps_extracted_evidence_and_tree_origins(tmp_path):
    from fireblade.core.case_package import export_package, import_package
    from fireblade.core.investigations import InvestigationLibrary
    from fireblade.core.sessions import read_session
    root = tmp_path/'volume'; (root/'var/log').mkdir(parents=True)
    (root/'var/log/auth.log').write_bytes(LOG)
    collection = DiskCollection(root, tmp_path/'work', ToolPack(tmp_path/'tools'))
    collection.parse()
    documents, active = read_session(collection.output/'collection.fireblade-session')
    library = InvestigationLibrary(tmp_path/'cases'); data = library.create('Disk portable')
    data = library.save(data['id'], documents, active,
        [dict(path=str(collection.output), name='Disk')], str(collection.output), data['revision'])
    archive = tmp_path/'case.fireblade-case'
    export_package(library, data, documents, active, archive, include_sources=True)
    target = InvestigationLibrary(tmp_path/'restored')
    restored = import_package(target, archive)['case']
    report = json.loads((Path(restored['active_collection'])/'collection.json').read_text())
    artifact = report['disk']['artifacts'][0]
    extracted = Path(artifact['extracted'])
    assert extracted.is_file() and extracted.read_bytes() == LOG
    assert extracted.is_relative_to(target.root)
    assert report['documents'][0]['navigation']['relative'] == 'var/log/auth.log'


def test_truncated_copy_is_rejected_without_partial_evidence(tmp_path):
    from io import BytesIO
    from types import SimpleNamespace
    root = tmp_path/'source'; root.mkdir()
    collection = DiskCollection(root, tmp_path/'work', ToolPack(tmp_path/'tools'))
    fake = SimpleNamespace(stat=lambda: SimpleNamespace(st_size=100, st_mtime_ns=0),
                           open=lambda mode: BytesIO(b'short'))
    with pytest.raises(ValueError, match='tronquée'):
        collection.copy_artifact(fake, 'volume', 'auth.log')
    assert collection.disk['extracted'] == 0
    assert not list(collection.root.rglob('*.partial'))
    assert not (collection.root/'volume/auth.log').exists()


def test_lowercase_registry_logs_are_copied_once_with_the_hive(tmp_path):
    root = tmp_path/'source'; root.mkdir()
    (root/'ntuser.dat').write_bytes(b'regf'+b'\0'*64)
    (root/'ntuser.dat.log1').write_bytes(b'log one')
    (root/'ntuser.dat.log2').write_bytes(b'log two')
    collection = DiskCollection(root, tmp_path/'work', ToolPack(tmp_path/'tools'))
    report = collection.parse()
    assert report['disk']['extracted'] == 3
    hive = next(e for e in report['files'] if e['path'].endswith('ntuser.dat'))
    assert len(hive['companions']) == 2
    assert (collection.root/'volume/ntuser.dat.log1').read_bytes() == b'log one'


def test_unverified_outputs_do_not_enter_the_saved_session(tmp_path):
    root = tmp_path/'source'; root.mkdir()
    collection = DiskCollection(root, tmp_path/'work', ToolPack(tmp_path/'tools'))
    collection.report['documents'] = [{'path': 'previous'}, {'path': 'unverified'}]
    collection.publish_results(1, dict(status='error'))
    assert collection.report['documents'] == [{'path': 'previous'}]


def test_windows_volume_extent_mapping_rejects_truncation():
    from fireblade.core.disk_destination import parse_windows_extents
    payload = bytearray(8+2*24)
    struct.pack_into('<I', payload, 0, 2)
    struct.pack_into('<I', payload, 8, 1)
    struct.pack_into('<I', payload, 32, 7)
    assert parse_windows_extents(payload) == {1, 7}
    with pytest.raises(ValueError): parse_windows_extents(payload[:-1])


def test_physical_destination_overlap_is_rejected_before_creating_case(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from fireblade.core import disk_destination
    source = tmp_path/'device'
    original_stat = Path.stat
    def device_stat(path, *args, **kwargs):
        if path == source:
            import stat
            return SimpleNamespace(st_mode=stat.S_IFBLK, st_rdev=123)
        return original_stat(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'stat', device_stat)
        patch.setattr(disk_destination, 'linux_backing_disks', lambda _: {'disk-A'})
        if disk_destination.os.name == 'nt':
            pytest.skip('Linux block-device mapping scenario')
        with pytest.raises(ValueError, match='autre disque physique'):
            DiskCollection(source, tmp_path/'work', ToolPack(tmp_path/'tools'), source_kind='physical')
    assert not (tmp_path/'work').exists()


def test_source_changed_after_parsing_is_not_published(tmp_path):
    root = tmp_path/'source'; (root/'var/log').mkdir(parents=True)
    source = root/'var/log/auth.log'; source.write_bytes(LOG)
    published = []
    collection = DiskCollection(root, tmp_path/'work', ToolPack(tmp_path/'tools'), ready=published.extend)
    original_import = collection.import_result
    def corrupt_after_import(*args, **kwargs):
        result = original_import(*args, **kwargs)
        extracted = collection.root/'volume/var/log/auth.log'
        extracted.write_bytes(LOG+b'changed\n')
        return result
    collection.import_result = corrupt_after_import
    report = collection.parse()
    assert not report['documents'] and not published
    assert report['files'][0]['status'] == 'error'
    assert 'modifiée' in report['files'][0]['error']
    assert source.read_bytes() == LOG


def test_windows_relative_paths_use_portable_separators(tmp_path):
    from pathlib import PureWindowsPath
    root = tmp_path/'source'; root.mkdir()
    source = root/'auth.log'; source.write_bytes(LOG)
    collection = DiskCollection(root, tmp_path/'work', ToolPack(tmp_path/'tools'))
    extracted = collection.copy_artifact(source, 'volume', PureWindowsPath('var/log/auth.log'))
    assert extracted == collection.root/'volume/var/log/auth.log'
    assert collection.disk['artifacts'][0]['relative'] == 'var/log/auth.log'
