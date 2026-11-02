import hashlib
import json
import zipfile

import pytest

from scripts.raw_pack.finalize import verify_archive
from scripts.raw_pack.package import ROOT


def fixture_zip(tmp_path, payload=b'raw bytes', replace=None):
    item = dict(path='01-Windows/evidence', bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest(), origin=dict(kind='public-native'))
    manifest = dict(raw_bytes=len(payload), files=[item])
    path = tmp_path / 'pack.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(ROOT + '/MANIFEST.json', json.dumps(manifest))
        archive.writestr(ROOT + '/' + item['path'], payload if replace is None else replace)
    return path


def test_small_archive_cannot_be_qualified_as_multi_gib_pack(tmp_path):
    with pytest.raises(ValueError, match='size'):
        verify_archive(fixture_zip(tmp_path))


def test_modified_zip_payload_is_rejected_before_publication(tmp_path):
    with pytest.raises(ValueError, match='mismatch'):
        verify_archive(fixture_zip(tmp_path, replace=b'bad bytes'))
