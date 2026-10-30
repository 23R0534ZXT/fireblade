import csv
import hashlib

import pytest

from fireblade.core import csv_chunks
from fireblade.core.engine import Case
from fireblade.core.errors import OperationCancelled
from fireblade.core.models import View


@pytest.mark.parametrize('delimiter', [',', ';', '\t', '|'])
def test_chunked_import_preserves_dialect_duplicates_multiline_and_record_order(tmp_path, monkeypatch, delimiter):
    monkeypatch.setattr(csv_chunks, 'CHUNK_BYTES', 8192)
    source = tmp_path / 'source.csv'
    values = [[str(i), f'"élève"{delimiter}日本語\r\nseconde ligne {i}', '', '0009007199254740993'] for i in range(1300)]
    with source.open('w', encoding='cp1252', newline='', errors='xmlcharrefreplace') as out:
        writer = csv.writer(out, delimiter=delimiter)
        writer.writerow(['A', 'A', '__row_id', 'ID'])
        writer.writerows(values)
    # The independently decoded source is the reference, including CRLF cells.
    with source.open(encoding='cp1252', newline='') as incoming:
        reader = csv.reader(incoming, delimiter=delimiter)
        next(reader)
        expected = [[v or None for v in row] for row in reader]
    case = Case(tmp_path / 'analysis.timeline')
    try:
        case.import_csv(source, encoding='cp1252')
        actual = case.db.execute('SELECT * FROM events ORDER BY __row_id').fetchall()
        assert actual == [(i+1, *row) for i, row in enumerate(expected)]
        target = tmp_path / 'export.csv'
        case.export(target, View())
        with target.open(encoding='utf-8-sig', newline='') as incoming:
            reader = csv.reader(incoming)
            assert next(reader) == case.headers
            assert [[v or None for v in row] for row in reader] == expected
        assert not list(tmp_path.glob('.fireblade-import-*'))
    finally:
        case.close()


def test_cancel_after_written_batch_rolls_back_and_cleans_up(tmp_path, monkeypatch):
    monkeypatch.setattr(csv_chunks, 'CHUNK_BYTES', 8192)
    source = tmp_path / 'source.csv'
    source.write_text('A,B\n' + ''.join(f'{i},value-{i}\n' for i in range(5000)), encoding='utf-8')
    digest = hashlib.sha256(source.read_bytes()).digest()
    case = Case(tmp_path / 'analysis.timeline')
    observed = []
    def progress(message):
        if message.endswith(' enregistrements écrits…'):
            observed.append(case.db.execute('SELECT count(*) FROM events').fetchone()[0])
            case.interrupt()
    try:
        with pytest.raises(OperationCancelled):
            case.import_csv(source, progress=progress)
        assert observed and 0 < observed[0] < 5000
        assert case.db.execute('SHOW TABLES').fetchall() == []
        assert case.headers == []
        assert not list(tmp_path.glob('.fireblade-import-*'))
        assert hashlib.sha256(source.read_bytes()).digest() == digest
        assert case.import_csv(source)['rows'] == 5000
    finally:
        case.close()


def test_late_invalid_width_rolls_back_all_batches(tmp_path, monkeypatch):
    monkeypatch.setattr(csv_chunks, 'CHUNK_BYTES', 8192)
    source = tmp_path / 'source.csv'
    # The invalid record is beyond the native 20,480-record sniff sample.
    source.write_text('A,B\n' + 'valid,value\n'*24000 + 'invalid,value,extra\n', encoding='utf-8')
    case = Case(tmp_path / 'analysis.timeline')
    try:
        with pytest.raises((ValueError, __import__('duckdb').InvalidInputException)):
            case.import_csv(source)
        assert case.db.execute('SHOW TABLES').fetchall() == []
        assert not list(tmp_path.glob('.fireblade-import-*'))
    finally:
        case.close()
