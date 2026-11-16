"""The text layer of a PDF is read; a scan is reported, never invented."""
import csv

import pytest

from fireblade.core import pdfreader
from pdf_sample import build_pdf


def test_a_pdf_with_a_text_layer_gives_its_lines_and_its_page(tmp_path):
    pytest.importorskip('pypdf')
    path = tmp_path/'facture.pdf'
    path.write_bytes(build_pdf('Paiement du 14/11/2026 confirmé'))

    produced, info = pdfreader.rows(path)

    assert info['status'] == 'ok' and info['pages'] == 1 and info['text_pages'] == 1
    assert produced and produced[0][1] == 1
    text = ' '.join(row[3] for row in produced)
    assert 'Paiement' in text and 'confirmé' in text
    assert produced[0][0].endswith('facture.pdf')


def test_the_csv_has_the_same_shape_as_every_other_reader(tmp_path):
    pytest.importorskip('pypdf')
    path = tmp_path/'facture.pdf'
    path.write_bytes(build_pdf('ligne unique'))
    target = tmp_path/'facture.csv'

    result = pdfreader.write_csv(path, target)

    rows = list(csv.reader(target.read_text(encoding='utf-8').splitlines()))
    assert rows[0] == list(pdfreader.HEADERS)
    assert result['rows'] == len(rows)-1 and result['kind'] == 'pdf'


def test_a_page_without_a_text_layer_is_a_scan_not_empty_rows(tmp_path):
    pytest.importorskip('pypdf')
    path = tmp_path/'scan.pdf'
    path.write_bytes(build_pdf(None))

    produced, info = pdfreader.rows(path)

    assert produced == []
    assert info['status'] == 'scanned' and info['text_pages'] == 0


def test_the_reader_says_so_when_the_extension_is_absent(monkeypatch):
    monkeypatch.setattr(pdfreader, 'backend', lambda: None)
    assert pdfreader.available() is False

    produced, info = pdfreader.rows('chemin/qui/n/existe/pas.pdf')

    assert produced == [] and info['status'] == 'missing'
