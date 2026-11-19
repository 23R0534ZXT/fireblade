"""Duplicates are decided on content, and a look-alike is told apart from a copy."""
import json
from pathlib import Path

from fireblade.core.collection import Collection


def entry(tmp_path, name, body, folder='a'):
    path = tmp_path/folder/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    import hashlib
    return dict(path=str(path), size=path.stat().st_size,
                sha256=hashlib.sha256(body).hexdigest(), status='pending')


class Bare:
    """Just enough of a Collection to exercise duplicate_of."""

    _seen = {}
    _similar = {}
    deduplicate_content = True

    def __init__(self, tmp_path):
        import threading
        self._seen = {}
        self._similar = {}
        self._seen_lock = threading.Lock()
        self.known = {}
        self.root = tmp_path

    duplicate_of = Collection.duplicate_of

    def event(self, name, **fields):
        return None

    def label_for(self, path):
        return Path(str(path)).name


def test_two_identical_files_are_one_piece_of_evidence(tmp_path):
    collection = Bare(tmp_path)
    first = entry(tmp_path, 'Security.evtx', b'EVTX' + b'x'*400, folder='a')
    copy = entry(tmp_path, 'Security - copie.evtx', b'EVTX' + b'x'*400, folder='b')
    assert collection.duplicate_of(first) is None
    assert collection.duplicate_of(copy) is copy
    assert copy['status'] == 'duplicate'
    assert copy['duplicate_of'] == first['path']


def test_two_files_that_only_look_alike_are_both_imported(tmp_path):
    collection = Bare(tmp_path)
    first = entry(tmp_path, 'Security.evtx', b'EVTX' + b'x'*400)
    lookalike = entry(tmp_path, 'Security.evtx', b'EVTX' + b'x'*399 + b'y', folder='b')
    assert collection.duplicate_of(first) is None
    assert collection.duplicate_of(lookalike) is None
    assert lookalike['status'] == 'pending', 'a different file was marked as a duplicate'
    assert lookalike['similar_to'] == first['path']


def test_a_copy_of_a_file_read_by_an_earlier_import_is_still_a_duplicate(tmp_path):
    collection = Bare(tmp_path)
    first = entry(tmp_path, 'amcache.hve', b'regf' + b'z'*300)
    collection.known = {first['sha256']: dict(path=first['path'], collection=str(tmp_path/'ancien'))}
    again = entry(tmp_path, 'amcache.hve', b'regf' + b'z'*300, folder='b')
    assert collection.duplicate_of(again) is again
    assert 'Already imported' in again['reason']
