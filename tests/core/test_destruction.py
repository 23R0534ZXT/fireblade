import base64
import hashlib
import os
from pathlib import Path

import pytest

from fireblade.core import destruction
from fireblade.core.destruction import destroy, load_records, plan, sha256_file, store_record
from fireblade.core.destruction_certificate import build, store_attachments, write

PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')


def case_folder(tmp_path):
    folder = tmp_path/'case'
    folder.mkdir()
    return folder


def witness_file(folder, name='artefact.bin', size=4096):
    path = folder/'collection'/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(range(256))*(size//256)+b'x'*(size % 256))
    return path


def test_three_passes_destroy_the_file_and_record_both_fingerprints(tmp_path):
    folder = case_folder(tmp_path)
    path = witness_file(folder)
    before = sha256_file(path)
    entries = plan([path], folder)
    record = destroy(entries, 'dod3', operator='M. Martin', witness='Mme Dupont', reason='Restitution')
    assert record['status'] == 'complete' and record['passes'] == 3
    item = record['files'][0]
    assert item['state'] == 'destroyed' and item['deleted'] and item['verified']
    assert item['sha256_before'] == before and len(item['sha256_after']) == 64
    assert not path.exists()
    assert record['finished'] and record['operator'] == 'M. Martin'
    assert 'wear levelling' in record['limitations']


def test_seven_passes_cross_chunk_boundaries(tmp_path):
    folder = case_folder(tmp_path)
    path = witness_file(folder, 'gros.bin', destruction.CHUNK + 1234)
    record = destroy(plan([path], folder), 'dod7', operator='analyste')
    assert record['passes'] == 7
    assert record['files'][0]['passes_done'] == 7 and record['files'][0]['verified']
    assert not path.exists()


def test_nothing_outside_the_case_folder_can_be_destroyed(tmp_path):
    folder = case_folder(tmp_path)
    outside = tmp_path/'ailleurs.txt'
    outside.write_text('preuve hors case')
    with pytest.raises(ValueError, match='outside the case folder'):
        plan([outside], folder)
    assert outside.read_text() == 'preuve hors case'


def test_a_directory_or_a_link_is_refused(tmp_path):
    folder = case_folder(tmp_path)
    (folder/'dossier').mkdir()
    with pytest.raises(ValueError, match='is a folder'):
        plan([folder/'dossier'], folder)
    link = folder/'lien.bin'
    try:
        link.symlink_to(witness_file(folder))
    except (OSError, NotImplementedError):
        pytest.skip('symlinks are not available on this host')
    with pytest.raises(ValueError, match='symbolic link'):
        plan([link], folder)


def test_cancellation_between_files_leaves_them_untouched(tmp_path):
    folder = case_folder(tmp_path)
    first = witness_file(folder, 'un.bin')
    second = witness_file(folder, 'deux.bin')
    record = destroy(plan([first, second], folder), 'dod3', cancel=lambda: True)
    assert record['status'] == 'partial'
    assert all(item['state'] == 'cancelled' for item in record['files'])
    assert first.exists() and second.exists()


def test_a_verification_failure_keeps_the_file_and_says_so(tmp_path):
    folder = case_folder(tmp_path)
    path = witness_file(folder)
    original = path.read_bytes()
    monkey = lambda *args, **kwargs: (False, '0'*64)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(destruction, '_verify', monkey)
        record = destroy(plan([path], folder), 'dod3')
    item = record['files'][0]
    assert record['status'] == 'partial' and item['state'] == 'failed'
    assert path.exists() and path.read_bytes() != original
    assert 'could not be verified' in item['error']


def test_a_read_only_file_is_destroyed_after_clearing_the_flag(tmp_path):
    folder = case_folder(tmp_path)
    path = witness_file(folder)
    os.chmod(path, 0o444)
    record = destroy(plan([path], folder), 'dod3')
    assert record['files'][0]['state'] == 'destroyed' and not path.exists()


def test_the_record_is_stored_in_the_case_and_read_back(tmp_path):
    folder = case_folder(tmp_path)
    path = witness_file(folder)
    record = destroy(plan([path], folder), 'dod3', operator='op')
    stored = store_record(folder, record)
    assert stored.parent.name == 'destruction' and stored.exists()
    records = load_records(folder)
    assert records and records[0]['id'] == record['id']


def test_the_certificate_names_the_client_the_hashes_and_the_limits(tmp_path):
    folder = case_folder(tmp_path)
    path = witness_file(folder)
    record = destroy(plan([path], folder), 'dod3', operator='M. Martin', witness='Mme Dupont',
                     reason='Fin de mission')
    photo = tmp_path/'photo.png'
    photo.write_bytes(PNG)
    record['attachments'] = store_attachments(folder, [photo], ['Poste après destruction'])
    document = build(record, case_name='Affaire 42', case_id='a'*32,
                     client=dict(name='ACME <script>', reference='REF-7', contact='M. Client'))
    html = document['html']
    assert 'Affaire 42' in html and 'ACME &lt;script&gt;' in html
    assert record['files'][0]['sha256_before'] in html
    assert 'Poste après destruction' in html and 'data:image/png;base64,' in html
    assert 'wear levelling' in html
    target = tmp_path/'certificat.html'
    write(target, document)
    assert 'Affaire 42' in target.read_text(encoding='utf-8')


def test_a_modified_photo_is_not_silently_included(tmp_path):
    folder = case_folder(tmp_path)
    path = witness_file(folder)
    record = destroy(plan([path], folder), 'dod3')
    photo = tmp_path/'photo.png'
    photo.write_bytes(PNG)
    record['attachments'] = store_attachments(folder, [photo], ['Capture'])
    Path(record['attachments'][0]['path']).write_bytes(PNG + b'tampered')
    html = build(record)['html']
    assert 'non incluse' in html and 'data:image/png;base64,' not in html


def test_the_certificate_is_also_a_pdf(tmp_path):
    folder = case_folder(tmp_path)
    path = witness_file(folder)
    record = destroy(plan([path], folder), 'dod3', operator='op')
    document = build(record, case_name='Case PDF')
    target = tmp_path/'certificat.pdf'
    write(target, document, pdf=True)
    data = target.read_bytes()
    assert data.startswith(b'%PDF-') and data.rstrip().endswith(b'%%EOF')
    assert (tmp_path/'certificat.pdf.partial').exists() is False
