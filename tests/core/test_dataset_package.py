import csv
import hashlib
import io
import json
import zipfile

from scripts.windows.package_dataset import package


def test_download_archive_contains_complete_CSV_with_matching_manifest_and_hashes(tmp_path):
    # Small unit fixture; the publication workflow enforces the actual 3-GiB size.
    folder = tmp_path / 'bundle'
    result = package(folder, target_bytes=64 * 1024)
    archive = folder / result['archive_name']
    with archive.open('rb') as incoming:
        assert hashlib.file_digest(incoming, 'sha256').hexdigest() == result['archive_sha256']
    with zipfile.ZipFile(archive) as incoming:
        payload = incoming.read('Fireblade-test-3GiB.csv')
        manifest = json.loads(incoming.read('dataset.json'))
    assert len(payload) == result['bytes']
    assert hashlib.sha256(payload).hexdigest() == result['sha256']
    reader = csv.reader(io.StringIO(payload.decode('utf-8-sig'), newline=''))
    assert next(reader) == result['headers']
    assert sum(1 for _ in reader) == result['rows']
    assert manifest['sha256'] == result['sha256']
    assert json.loads((folder / 'publication.json').read_text()) == result
    assert (folder / 'SHA256SUMS.txt').read_text().splitlines() == [
        result['archive_sha256'] + '  Fireblade-test-3GiB.zip',
        result['sha256'] + '  Fireblade-test-3GiB.csv']
