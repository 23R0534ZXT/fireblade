"""The report promises reversible, traceable actions on evidence."""
import csv
from pathlib import Path

import pytest

from fireblade.core import report_actions as actions


def entry(path, status='unsupported', **extra):
    value = {'path': str(path), 'status': status, 'tools': [], 'error': ''}
    value.update(extra)
    return value


def test_unprocessed_selects_only_files_without_analysis():
    entries = [entry('a', 'unsupported'), entry('b', 'complete'), entry('c', 'error'),
               entry('d', 'skipped'), entry('e', 'complete_with_warnings')]
    assert [e['path'] for e in actions.unprocessed(entries)] == ['a', 'c', 'd']


def test_copy_keeps_the_tree_and_never_moves_the_evidence(tmp_path):
    root = tmp_path / 'evidence'
    (root / 'var' / 'log').mkdir(parents=True)
    source = root / 'var' / 'log' / 'weird.bin'
    source.write_bytes(b'inconnu')
    entries = [entry(source), entry(root / 'var' / 'log' / 'absent.bin', 'error')]

    result = actions.copy_unprocessed(entries, tmp_path / 'non traites', root)

    copied = Path(result['copied'][0])
    assert copied.exists() and copied.read_bytes() == b'inconnu'
    assert (tmp_path / 'non traites' / 'var' / 'log' / 'weird.bin').read_bytes() == b'inconnu'
    assert source.exists(), "la preuve ne doit jamais être déplacée"
    assert result['failed'] and 'introuvable' in result['failed'][0][1]


def test_copy_can_be_repeated_without_overwriting(tmp_path):
    root = tmp_path / 'evidence'
    root.mkdir()
    source = root / 'file.bin'
    source.write_bytes(b'x')
    entries = [entry(source)]
    first = actions.copy_unprocessed(entries, tmp_path / 'out', root)
    second = actions.copy_unprocessed(entries, tmp_path / 'out', root)
    assert first['copied'] and not second['copied']
    assert second['skipped']


def test_export_writes_every_visible_column_in_utf8(tmp_path):
    target = tmp_path / 'liste.csv'
    entries = [entry('C:/preuves/éléphant.pdf', 'unsupported', error='extension non prise en charge')]
    actions.export_rows(entries, target)
    rows = list(csv.reader(target.read_text(encoding='utf-8-sig').splitlines()))
    assert rows[0][:3] == ['État', 'Fichier', 'Lecteurs']
    assert rows[1][0] == 'unsupported' and 'éléphant.pdf' in rows[1][1]
    assert rows[1][3] == 'extension non prise en charge'


def test_removing_a_source_requires_the_recorded_hash(tmp_path):
    source = tmp_path / 'note.txt'
    source.write_bytes(b'contenu initial')
    recorded = actions.sha256_file(source)

    with pytest.raises(ValueError):
        actions.remove_source(entry(source, sha256='0' * 64))

    record = actions.remove_source(entry(source, sha256=recorded))
    assert record['status'] == 'deleted' and record['sha256'] == recorded
    assert not source.exists()


def test_removing_a_changed_file_is_refused(tmp_path):
    source = tmp_path / 'note.txt'
    source.write_bytes(b'avant')
    recorded = actions.sha256_file(source)
    source.write_bytes(b'apres')
    with pytest.raises(ValueError):
        actions.remove_source(entry(source, sha256=recorded))
    assert source.exists(), 'un fichier modifié ne doit jamais être supprimé'


def test_ignoring_keeps_the_state_and_is_reversible(tmp_path):
    item = entry(tmp_path / 'x.pdf', error='extension non prise en charge')
    actions.set_ignored(item)
    assert item['ignored'] is True and item['status'] == 'unsupported'
    actions.set_ignored(item, False)
    assert 'ignored' not in item
