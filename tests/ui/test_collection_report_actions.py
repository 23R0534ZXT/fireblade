"""The import report must explain itself, and its preview must never fail."""
from pathlib import Path

import pytest

from fireblade.ui import collection_report as report


def entry(status='unsupported', **extra):
    value = {'path': 'C:/preuves/fichier', 'status': status, 'tools': [], 'error': ''}
    value.update(extra)
    return value


def test_preview_reads_text_and_reports_an_empty_file(tmp_path):
    path = tmp_path / 'journal.log'
    path.write_text('ligne un\nligne deux\n', encoding='utf-8')
    assert report.preview_text(path).startswith('ligne un')
    empty = tmp_path / 'vide.bin'
    empty.touch()
    assert '0 octet' in report.preview_text(empty)


def test_preview_shows_binary_as_bytes_instead_of_mojibake(tmp_path):
    path = tmp_path / 'opaque.bin'
    path.write_bytes(bytes(range(256)))
    text = report.preview_text(path)
    assert '00000000' in text and '00 01 02 03' in text


def test_preview_falls_back_to_cp1252_for_latin_text(tmp_path):
    path = tmp_path / 'latin.csv'
    path.write_bytes('ville;Orléans\n'.encode('cp1252'))
    assert 'Orléans' in report.preview_text(path)


def test_preview_truncates_a_large_file_without_failing(tmp_path):
    path = tmp_path / 'gros.log'
    path.write_bytes(b'a' * 5000)
    text = report.preview_text(path, limit=1024)
    assert 'Aperçu tronqué' in text and len(text) < 3000


def test_preview_of_a_missing_file_is_a_message_not_a_crash(tmp_path):
    assert 'illisible' in report.preview_text(tmp_path / 'absent.bin')


def test_outcome_puts_an_ignored_entry_out_of_the_counts():
    assert report.outcome(entry('unsupported', ignored=True)) == 'ignored'
    assert report.outcome(entry('complete', ignored=True)) == 'ignored'


def test_outcome_classifies_every_state_used_by_the_report():
    assert report.outcome(entry('complete')) == 'complete'
    assert report.outcome(entry('unsupported')) == 'unsupported'
    assert report.outcome(entry('deleted')) == 'unsupported'
    assert report.outcome(entry('error')) == 'errors'
    assert report.outcome(entry('attention')) == 'warnings'
    assert report.outcome(entry('attention', runs=[{'status': 'error'}])) == 'errors'
    assert report.outcome(entry('companion')) == 'other'
