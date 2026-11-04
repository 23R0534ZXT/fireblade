"""Independent 0.2.0 audit probes; synthetic data, no publication or production edits.

Run with a NEW --directory. Findings are recorded separately from unexpected
probe errors. --disk-fixtures accepts the pinned public fixtures documented in
the audit report. Only --fetch-fixtures makes network requests.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
from pathlib import Path
import platform
import random
import sqlite3
import subprocess
import time
import traceback
import urllib.request
from unittest.mock import patch
import zipfile

import duckdb

from fireblade.core import csv_chunks
from fireblade.core.case_package import import_package
from fireblade.core.collection import Collection, ToolPack
from fireblade.core.disk import DiskCollection
from fireblade.core.engine import Case
from fireblade.core.investigations import InvestigationLibrary
from fireblade.core.models import Filter, FilterGroup, View
from fireblade.core.sessions import read_session


PUBLIC_FIXTURES = [
    ('dissect.extfs', '24cb5825b139d7734c41a0abc777afe96546d472', 'tests/data/ext4.bin.gz',
     '913f98e158505e6c3b1de4a70861c46c9d725ced641334fa015509a92f4682f4'),
    ('dissect.ntfs', '7f021dd1182eb6f9b6a2dbd19cf2e29143ea654d', 'tests/_data/ntfs.bin.gz',
     'cc1b5c665a80befed008b3db817325aac1555e1efe511de63203f421c2250080'),
    ('dissect.evidence', 'b2d1ac23288a0a77b1e6158b2dfcad0c945c5d2d', 'tests/_data/ewf/single/image.E01',
     'fbc3da213475f9692be6bf00fb68eb87adaab3195c204f21ea42efc3b2b35097'),
]


def fetch_fixtures(directory):
    """Opt-in, bounded downloads, verified against public Git LFS object hashes."""
    directory.mkdir(parents=True, exist_ok=False)
    provenance = []
    for repository, commit, name, expected in PUBLIC_FIXTURES:
        url = f'https://media.githubusercontent.com/media/fox-it/{repository}/{commit}/{name}'
        with urllib.request.urlopen(url, timeout=60) as incoming:
            data = incoming.read(2*1024**2+1)
        if len(data) > 2*1024**2 or hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Public fixture size or SHA-256 mismatch: '+name)
        path = directory/Path(name).name; path.write_bytes(data)
        if path.suffix == '.gz':
            with gzip.open(path, 'rb') as compressed:
                decoded = compressed.read(32*1024**2+1)
            if len(decoded) > 32*1024**2:
                raise ValueError('Expanded public fixture exceeds 32 MiB')
            path = path.with_suffix(''); path.write_bytes(decoded)
        provenance.append(dict(repository=repository, commit=commit, url=url,
                               sha256_download=expected, path=str(path), sha256=sha(path), bytes=path.stat().st_size))
    (directory/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n', encoding='utf-8')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def differential_csv(root):
    rng = random.Random(20261103)
    atoms = ['', 'NULL', '00001', '900719925474099312345', 'élève 😀',
             'quoted " value', 'multiline\nrecord', 'comma,semi;tab\tpipe|',
             'x\0y', '=1+1', "'); DROP TABLE events; --", ' trailing ']
    headers = ['ID', 'User', 'Description', 'Number', 'Unicode', 'Odd"Header']
    rows = [[rng.choice(atoms) for _ in headers] for _ in range(37)]
    scenarios = 0
    for delimiter in (',', ';', '\t', '|'):
        for encoding in ('utf-8', 'utf-8-sig', 'utf-16', 'utf-32', 'utf-16-be'):
            for chunked in (False, True):
                folder = root/str(scenarios); folder.mkdir()
                source = folder/'source.csv'
                with source.open('w', encoding=encoding, newline='') as stream:
                    writer = csv.writer(stream, delimiter=delimiter)
                    writer.writerow(headers); writer.writerows(rows)
                before = sha(source)
                with source.open(encoding=encoding, newline='') as stream:
                    parsed = list(csv.reader(stream, delimiter=delimiter))
                expected = [tuple([n]+[v if v != '' else None for v in row])
                            for n, row in enumerate(parsed[1:], 1)]
                case = Case(folder/'analysis.timeline')
                try:
                    with patch.object(csv_chunks, 'CHUNK_BYTES', 96 if chunked else 16*1024**2):
                        case.import_csv(source, delimiter=delimiter, encoding=encoding)
                    assert case.headers == headers
                    assert case.page(View(), limit=1000) == expected
                    exported = folder/'export.csv'
                    receipt = case.export(exported, View())
                    assert receipt['verified_rows'] == len(expected)
                    with exported.open(encoding='utf-8-sig', newline='') as stream:
                        assert list(csv.reader(stream)) == parsed
                    assert sha(source) == before
                finally:
                    case.close()
                reopened = Case(folder/'analysis.timeline')
                try:
                    assert reopened.page(View(), limit=1000) == expected
                finally:
                    reopened.close()
                scenarios += 1
    return dict(scenarios=scenarios, rows_per_scenario=len(rows), oracle='stdlib csv.reader',
                checks=['exact cells', 'header quoting', 'forced chunk path', 'export', 'reopen', 'unchanged source'])


def filter_oracle(root):
    rng = random.Random(20261103)
    atoms = ['', 'alice', 'bob', 'Alice', 'élève', 'a,b', "x' OR 1=1 --"]
    rows = [[rng.choice(atoms), str(rng.randrange(-500, 500))] for _ in range(200)]
    source = root/'source.csv'
    with source.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream); writer.writerow(['User', 'Number']); writer.writerows(rows)
    def evaluate(item, row):
        if isinstance(item, FilterGroup):
            children = [evaluate(child, row) for child in item.children]
            if item.logic == 'not': return not bool(children[0])
            if item.logic == 'and': return False if False in children else None if None in children else True
            return True if True in children else None if None in children else False
        value = row[item.column] or None
        op, target = item.operator, item.value
        if op == 'empty': return value is None
        if op == 'ne': return value != target
        if op == 'eq': return None if value is None else value == target
        if op in ('gt', 'le'): return int(value) > int(target) if op == 'gt' else int(value) <= int(target)
        value = (value or '').lower(); target = target.lower()
        return {'contains': lambda: target in value, 'starts': lambda: value.startswith(target),
                'ends': lambda: value.endswith(target)}[op]()
    def condition(depth=0):
        if depth < 3 and rng.random() < .6:
            logic = rng.choice(['and', 'or', 'not'])
            return FilterGroup(logic, [condition(depth+1) for _ in range(1 if logic == 'not' else rng.randrange(1, 4))])
        if rng.random() < .25: return Filter(1, rng.choice(['gt', 'le']), str(rng.randrange(-500, 500)))
        return Filter(0, rng.choice(['eq', 'ne', 'contains', 'starts', 'ends', 'empty']), rng.choice(atoms))
    case = Case(root/'analysis.timeline')
    try:
        case.import_csv(source)
        for _ in range(250):
            item = condition(); view = View(expression=item)
            expected = [n for n, row in enumerate(rows, 1) if evaluate(item, row) is True]
            actual = [row[0] for row in case.page(view, limit=1000)]
            assert actual == expected, (view.to_json(), actual, expected)
            assert case.count(view) == len(expected)
    finally:
        case.close()
    return dict(queries=250, rows=200, seed=20261103, oracle='Python three-valued boolean evaluator')


def timestamp_oracle(root):
    rng = random.Random(42); values = []; epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    for _ in range(300):
        base = datetime(rng.choice([1601, 1969, 1970, 2026, 2263]), rng.randrange(1, 13), rng.randrange(1, 28),
                        rng.randrange(24), rng.randrange(60), rng.randrange(60))
        ns = rng.randrange(10**9); offset = rng.choice([-720, -60, 0, 60, 330, 840])
        zone = timezone(timedelta(minutes=offset)); stamp = base.replace(tzinfo=zone)
        delta = stamp.astimezone(timezone.utc)-epoch
        value = base.isoformat()+f'.{ns:09d}'+stamp.isoformat()[-6:]
        values.append((value, (delta.days*86400+delta.seconds)*10**9+ns))
    from fireblade.core.timestamps import timestamp_key
    db = duckdb.connect()
    try:
        db.execute('CREATE TABLE input(value VARCHAR)')
        db.executemany('INSERT INTO input VALUES (?)', [(value,) for value, _ in values])
        actual = [row[0] for row in db.execute('SELECT '+timestamp_key('value')+' FROM input').fetchall()]
        assert actual == [expected for _, expected in values]
    finally:
        db.close()
    return dict(timestamps=len(values), years=[1601, 1969, 1970, 2026, 2263], fractional_digits=9,
                oracle='integer UTC epoch deltas calculated with datetime')


def sqlite_wal(root):
    volume = root/'volume'; volume.mkdir(); source = volume/'History'
    producer = sqlite3.connect(source)
    reader = None
    try:
        producer.execute('PRAGMA journal_mode=WAL')
        producer.execute('CREATE TABLE visits(url TEXT)'); producer.commit()
        producer.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        producer.execute("INSERT INTO visits VALUES ('https://marker.example.test/committed')"); producer.commit()
        original_count = producer.execute('SELECT count(*) FROM visits').fetchone()[0]
        disk = DiskCollection(volume, root/'work', ToolPack(root/'none'))
        list(disk.walk_sources(lambda _: None))
        copied = Path(disk.disk['artifacts'][0]['extracted'])
        copied_before_read = sorted(p.name for p in copied.parent.iterdir())
        reader = sqlite3.connect(f'file:{copied}?mode=ro', uri=True)
        copied_count = reader.execute('SELECT count(*) FROM visits').fetchone()[0]
        return dict(finding=original_count != copied_count, priority='P1',
                    source_rows=original_count, copied_rows=copied_count, copied_before_read=copied_before_read,
                    source_files=sorted(p.name for p in volume.iterdir()), errors=disk.disk['errors'],
                    sha256_main_matches=sha(source) == sha(copied))
    finally:
        if reader: reader.close()
        producer.close()


def changed_source(root):
    source = root/'input'; source.mkdir(); path = source/'data.csv'; path.write_text('ID,User\n001,alice\n')
    collector = Collection(source, root/'work', ToolPack(root/'none'))
    original = collector.import_result
    def mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        path.write_text('ID,User\n002,bob\n')
        return result
    collector.import_result = mutate
    report = collector.parse()
    session = collector.output/'collection.fireblade-session'
    documents = read_session(session)[0] if session.exists() else []
    return dict(finding=report['files'][0]['status'] == 'error' and bool(documents), priority='P2',
                collection_status=report['status'], file_status=report['files'][0]['status'],
                diagnostic=report['files'][0]['error'], saved_documents=len(documents))


def hostile_package(root):
    marker = root/'outside-archive.txt'; marker.write_text('SYNTHETIC-LOCAL-MARKER-ONLY')
    source = root/'source.csv'; source.write_text('Value\noriginal evidence\n')
    database = root/'attack.timeline'; case = Case(database)
    try: info = case.import_csv(source)
    finally: case.close()
    db = duckdb.connect(str(database))
    try:
        db.execute('DROP TABLE events')
        quoted = str(marker).replace("'", "''")
        db.execute(f"CREATE VIEW events AS SELECT 1::BIGINT AS __row_id, content AS c0 FROM read_text('{quoted}')")
    finally:
        db.close()
    library = InvestigationLibrary(root/'original'); original = library.create('Synthetic malicious package')
    member = 'analyses/0000.timeline'
    manifest = dict(format='fireblade-case-package', version=1, case=original,
                    documents=[dict(database=member, source=info, view=json.loads(View().to_json()), header='')],
                    active=0, files=[dict(path=member, size=database.stat().st_size, sha256=sha(database))],
                    collections=[], relocation={str(database): member}, missing_sources=[str(source)])
    archive = root/'attack.fireblade-case'
    with zipfile.ZipFile(archive, 'w') as output:
        output.write(database, member); output.writestr('manifest.json', json.dumps(manifest))
    target = InvestigationLibrary(root/'target')
    try:
        imported = import_package(target, archive)
    except (ValueError, duckdb.Error) as error:
        assert target.list() == ([], [])
        return dict(finding=False, rejected=True, reason=str(error), no_case_published=True)
    snapshots, _ = read_session(target.session_path(imported['case']))
    restored = Case(snapshots[0].path)
    try:
        rows = restored.page(View())
        return dict(finding=rows[0][1] == marker.read_text(), priority='P1', import_succeeded=True,
                    external_marker_displayed=rows[0][1], files_declared=1,
                    marker_in_archive=False, warning='Synthetic marker only; no user secrets read')
    finally:
        restored.close()


def large_oracle(root, directory):
    database = directory/'benchmark.timeline'; source = directory/'benchmark.csv'
    before = sha(source); case = Case(database, memory_mb=256)
    try:
        count = case.count(View()); assert count == 8380000
        for offset in (0, 9999, 10000, count//2, count-250, count, count+10):
            rows = case.page(View(), offset=offset)
            for n, row in enumerate(rows, offset+1):
                i = (n-1) % 10000
                assert row == (n, '2026-01-01 12:00:00', str(i%12), 'user'+str(i%80),
                               '000'+str(i), f'C:\\Windows\\System32\\file{i}.dll', 'artifact detail '*20)
            assert len(rows) == max(0, min(250, count-offset))
        group = {row[0]: row[1] for row in case.page(View(groups=[1]))}
        assert group == {str(n): sum(i%12 == n for i in range(10000))*838 for n in range(12)}
        view = View(filters=[Filter(2, 'eq', 'user42')])
        expected_ids = [i+1 for i in range(10000) if i%80 == 42]
        assert case.count(view) == len(expected_ids)*838
        receipt = case.export(root/'filtered.csv', view)
        observed = 0
        with (root/'filtered.csv').open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.reader(stream); next(reader)
            for block in range(838):
                for row_id in expected_ids:
                    i = row_id-1
                    assert next(reader) == ['2026-01-01 12:00:00', str(i%12), 'user42', '000'+str(i),
                                            f'C:\\Windows\\System32\\file{i}.dll', 'artifact detail '*20]
                    observed += 1
            assert next(reader, None) is None
        assert receipt['verified_rows'] == observed
        assert sha(source) == before
        return dict(rows=count, independent_export_rows=observed, offsets=7, source_sha256=before)
    finally:
        case.close()


def disk_matrix(root, directory):
    from dissect.target import Target
    results = []
    for name in ('ext4.bin', 'ntfs.bin'):
        source = directory/name; before = sha(source); item = dict(source=str(source))
        try:
            target = Target.open(source)
            try:
                item['root_entries'] = [sorted(p.name for p in fs.path('/').iterdir()) for fs in target.filesystems]
                if name == 'ext4.bin':
                    assert target.filesystems[0].path('/test_file').read_bytes() == b'dissect test file in ext4\n'
            finally:
                for disk in target.disks: disk.close()
            collector = DiskCollection(source, root/(name+'-work'), ToolPack(root/'none'), source_kind='image')
            report = collector.parse()
            item.update(status=report['status'], extracted=report['disk']['extracted'], errors=report['disk']['errors'])
        except Exception as error:
            item.update(status='failed', error=repr(error), traceback=traceback.format_exc())
        item['source_unchanged'] = sha(source) == before
        results.append(item)
    from dissect.evidence.ewf.ewf import EWF
    image = directory/'image.E01'; before = sha(image)
    with image.open('rb') as incoming:
        ewf = EWF(incoming)
        assert ewf.size == 4*1024**2+16
        stream = ewf.open()
        for n in range(1024): assert stream.read(4096) == bytes([n%256])*4096
        assert stream.read().startswith(b'kusjes van SRT<3')
    assert sha(image) == before
    results.append(dict(source=str(image), status='passed', scope='container decoding only; fixture has no filesystem'))
    return dict(finding=any(item['status'] == 'failed' for item in results), priority='P1', results=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--large-directory', type=Path)
    parser.add_argument('--disk-fixtures', type=Path)
    parser.add_argument('--fetch-fixtures', type=Path, help='Download pinned public images to a NEW directory')
    args = parser.parse_args()
    if args.fetch_fixtures and args.disk_fixtures:
        parser.error('Choose either --fetch-fixtures or --disk-fixtures')
    args.directory.mkdir(parents=True, exist_ok=False)
    if args.fetch_fixtures:
        fetch_fixtures(args.fetch_fixtures)
        args.disk_fixtures = args.fetch_fixtures
    report = dict(format='fireblade-v020-independent-audit', version=1, platform=platform.platform(),
                  python=platform.python_version(), duckdb=duckdb.__version__, checks=[])
    report['commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    probes = [('differential_csv', differential_csv), ('filter_oracle', filter_oracle),
              ('timestamp_oracle', timestamp_oracle), ('sqlite_wal', sqlite_wal),
              ('changed_source', changed_source), ('hostile_package', hostile_package)]
    if args.large_directory: probes.append(('large_oracle', lambda root: large_oracle(root, args.large_directory)))
    if args.disk_fixtures: probes.append(('disk_matrix', lambda root: disk_matrix(root, args.disk_fixtures)))
    for name, probe in probes:
        root = args.directory/name; root.mkdir(); started = time.monotonic()
        try:
            details = probe(root)
            result = dict(name=name, status='finding' if details.get('finding') else 'passed', details=details)
        except Exception as error:
            result = dict(name=name, status='error', error=repr(error), traceback=traceback.format_exc())
        result['seconds'] = round(time.monotonic()-started, 3); report['checks'].append(result)
        report['counts'] = dict(Counter(check['status'] for check in report['checks']))
        (args.directory/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False), flush=True)
    if report['counts'].get('error'): raise SystemExit(2)
    if report['counts'].get('finding'): raise SystemExit(1)


if __name__ == '__main__': main()
