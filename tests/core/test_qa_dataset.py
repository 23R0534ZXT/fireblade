from collections import Counter
import csv
import hashlib
from scripts.windows.dataset import generate


def test_dataset_reference_matches_independent_CSV_readback(tmp_path):
    spec=generate(tmp_path/'data',64*1024)
    source=__import__('pathlib').Path(spec['source'])
    with source.open('rb') as incoming:assert hashlib.file_digest(incoming,'sha256').hexdigest()==spec['sha256']
    with source.open(encoding='utf-8-sig',newline='') as incoming:
        reader=csv.reader(incoming);assert next(reader)==spec['headers']
        records=list(reader)
    assert len(records)==spec['rows']
    assert len({row[12] for row in records})==len(records)
    assert spec['reference']['user042']==sum(row[3]=='user042' for row in records)
    assert spec['reference']['empty_user']==sum(row[3]=='' for row in records)
    counts=Counter(row[1] or None for row in records)
    assert counts==dict(spec['groups'][0]['levels'][0]['expected'])
    for index,values in spec['samples'].items():assert [v or None for v in records[int(index)-1]]==values
    assert '\n' in records[137][14] and '日本語' in records[137][15]
    from fireblade.core.engine import Case
    from fireblade.core.models import View
    case=Case(tmp_path/'roundtrip.timeline')
    try:
        case.import_csv(source)
        target=tmp_path/'export.csv'
        case.export(target,View())
        with target.open('rb') as incoming:
            assert hashlib.file_digest(incoming,'sha256').hexdigest()==spec['sha256']
    finally:case.close()
