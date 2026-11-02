import io
from pathlib import Path

import pytest

from scripts.raw_pack.package import download, safe_relative, write_linux_file
from fireblade.core.catscale import records


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'a\\escape', 'C:/escape', 'a/../b', 'a\x00b'])
def test_raw_source_paths_cannot_escape(name):
    with pytest.raises(ValueError):
        safe_relative(name)


def test_download_rejects_wrong_hash_without_publishing_partial_file(tmp_path, monkeypatch):
    monkeypatch.setattr('urllib.request.urlopen', lambda *args, **kwargs: io.BytesIO(b'wrong content'))
    target = tmp_path / 'source'
    with pytest.raises(ValueError, match='mismatch'):
        download('https://example.test/source', target, '0' * 64)
    assert not target.exists() and not list(tmp_path.glob('*.partial'))


@pytest.mark.parametrize('kind', ['auth', 'audit', 'syslog'])
def test_generated_raw_logs_parse_with_exact_line_counts_and_landmarks(tmp_path, kind):
    path = tmp_path / 'catscale_out' / 'Logs' / (kind + '.log')
    result = write_linux_file(path, 'lab-edge-01', kind, 256 * 1024)
    with path.open(encoding='utf-8') as stream:
        parsed = list(records(enumerate((line.rstrip('\n') for line in stream), 1), path, []))
    assert len(parsed) == result['lines']
    assert all(row['Lecture'] == 'Structurée' for row in parsed)
    assert result['landmarks']
    for landmark in result['landmarks']:
        assert landmark['text'] == parsed[landmark['line'] - 1]['Texte brut']
    if kind == 'auth':
        assert 'Failed password for backup from 198.51.100.42' in parsed[1000]['Texte brut']
        assert 'Accepted password for backup from 198.51.100.42' in parsed[1001]['Texte brut']
