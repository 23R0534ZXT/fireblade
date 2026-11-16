"""One large file reads in ranges, and must give exactly the rows of a whole read."""
import csv

from fireblade.core import linux_logs, linux_slices
from fireblade.core.parse_pool import ParsePool


def build(path, count=400):
    with path.open('w', encoding='utf-8', newline='') as stream:
        for index in range(1, count + 1):
            stream.write(f'Jan  2 03:04:{index % 60:02d} host sshd[{index}]: '
                         f'Accepted password for root from 10.0.1.{index % 250} port 22 ssh2\n')
    return path


def read_rows(csv_path):
    with open(csv_path, encoding='utf-8', newline='') as stream:
        return list(csv.reader(stream))


def split(monkeypatch, source, parts):
    monkeypatch.setattr(linux_slices, 'MIN_SLICE_BYTES', 0)
    return linux_slices.plan(source, parts)


def test_the_ranges_start_on_a_line_boundary_with_their_line_number(tmp_path, monkeypatch):
    source = build(tmp_path / 'access.log')
    spans = split(monkeypatch, source, 4)

    assert len(spans) == 4
    assert spans[0]['start'] == 0 and spans[0]['line'] == 1
    assert spans[-1]['end'] == source.stat().st_size
    data = source.read_bytes()
    for span in spans[1:]:
        assert data[span['start'] - 1:span['start']] == b'\n'
        assert data[:span['start']].count(b'\n') + 1 == span['line']
    for previous, span in zip(spans, spans[1:]):
        assert previous['end'] == span['start']


def test_a_sliced_read_gives_the_rows_of_a_whole_read(tmp_path, monkeypatch):
    source = build(tmp_path / 'access.log')
    whole_folder = tmp_path / 'whole'
    whole_folder.mkdir()
    whole = linux_logs.parse(source, whole_folder)['outputs'][0]['csv']

    spans = split(monkeypatch, source, 4)
    folder = tmp_path / 'sliced'
    folder.mkdir()
    results = []
    for index, span in enumerate(spans):
        destination = folder / str(index)
        destination.mkdir()
        results.append(linux_logs.parse(source, destination, span=span))
    merged = linux_slices.merge(folder, source, results)

    assert merged['members'][0]['rows'] == sum(
        result['members'][0]['rows'] for result in results)
    assert merged['members'][0]['rows'] == 400
    assert merged['members'][0]['status'] == 'complete'
    assert read_rows(merged['outputs'][0]['csv']) == read_rows(whole)


def test_a_compressed_or_wide_file_is_not_split(tmp_path, monkeypatch):
    gzip_like = tmp_path / 'auth.log'
    gzip_like.write_bytes(b'\x1f\x8b' + b'0' * 5000 + b'\n')
    wide = tmp_path / 'auth-utf16.log'
    wide.write_bytes('Jan  2 03:04:05 host sshd[1]: hi\n'.encode('utf-16-le') * 20)
    header = tmp_path / 'zeek.log'
    header.write_text('#separator \\x09\n#fields\tts\tid.orig_h\n1\t10.0.0.1\n' * 40, encoding='utf-8')

    monkeypatch.setattr(linux_slices, 'MIN_SLICE_BYTES', 0)
    assert linux_slices.plan(gzip_like, 4) == []
    assert linux_slices.plan(wide, 4) == []
    assert linux_slices.plan(header, 4) == []


def test_a_small_file_is_not_split(tmp_path):
    source = build(tmp_path / 'auth.log', count=5)
    assert linux_slices.plan(source, 8) == []


def test_a_batch_reads_the_ranges_in_order(tmp_path, monkeypatch):
    source = build(tmp_path / 'access.log', count=300)
    spans = split(monkeypatch, source, 3)
    folder = tmp_path / 'batch'
    jobs = []
    for index, span in enumerate(spans):
        destination = folder / str(index)
        destination.mkdir(parents=True)
        jobs.append(dict(source=str(source), output=str(destination), span=dict(span)))

    pool = ParsePool(3).start()
    try:
        results = pool.run_many(jobs)
    finally:
        pool.close()

    assert len(results) == 3
    assert all(result['outputs'] for result in results)
    assert sum(result['members'][0]['rows'] for result in results) == 300
