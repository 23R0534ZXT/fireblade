"""The text layer of a PDF is read; a scan is reported, never invented."""

import csv

import pytest
from pdf_sample import build_pdf

from fireblade.core import pdfreader


def test_a_pdf_with_a_text_layer_gives_its_lines_and_its_page(tmp_path):
    pytest.importorskip("pypdf")
    path = tmp_path / "facture.pdf"
    path.write_bytes(build_pdf("Paiement du 14/11/2026 confirmé"))

    produced, info = pdfreader.rows(path)

    assert info["status"] == "ok" and info["pages"] == 1 and info["text_pages"] == 1
    assert produced and produced[0][1] == 1
    text = " ".join(row[3] for row in produced)
    assert "Paiement" in text and "confirmé" in text
    assert produced[0][0].endswith("facture.pdf")


def test_the_csv_has_the_same_shape_as_every_other_reader(tmp_path):
    pytest.importorskip("pypdf")
    path = tmp_path / "facture.pdf"
    path.write_bytes(build_pdf("ligne unique"))
    target = tmp_path / "facture.csv"

    result = pdfreader.write_csv(path, target)

    rows = list(csv.reader(target.read_text(encoding="utf-8").splitlines()))
    assert rows[0] == list(pdfreader.HEADERS)
    assert result["rows"] == len(rows) - 1 and result["kind"] == "pdf"


def test_every_page_keeps_its_own_number(tmp_path):
    pytest.importorskip("pypdf")
    path = tmp_path / "bundle.pdf"
    path.write_bytes(build_pdf(["page un", "page deux", "page trois"], pages=3))

    produced, info = pdfreader.rows(path)

    assert info["pages"] == 3 and info["text_pages"] == 3
    assert [row[1] for row in produced] == [1, 2, 3]
    assert [row[3] for row in produced] == ["page un", "page deux", "page trois"]


def test_a_page_without_text_does_not_hide_the_others(tmp_path):
    pytest.importorskip("pypdf")
    path = tmp_path / "mixte.pdf"
    path.write_bytes(build_pdf(["lisible", None], pages=2))

    produced, info = pdfreader.rows(path)

    assert info["pages"] == 2 and info["text_pages"] == 1 and info["status"] == "ok"
    assert [row[3] for row in produced] == ["lisible"]


def test_a_scanned_pdf_is_reported_as_scanned_not_empty_rows(tmp_path):
    pytest.importorskip("pypdf")
    path = tmp_path / "scan.pdf"
    path.write_bytes(build_pdf(None))

    produced, info = pdfreader.rows(path)

    assert produced == []
    assert info["status"] == "scanned" and info["text_pages"] == 0


def test_the_reader_says_so_when_the_extension_is_absent(monkeypatch):
    monkeypatch.setattr(pdfreader, "backend", lambda: None)
    assert pdfreader.available() is False

    produced, info = pdfreader.rows("chemin/qui/n/existe/pas.pdf")

    assert produced == [] and info["status"] == "missing"


def encrypted_pdf(source, target, password="ouvre-toi"):
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    writer.append(PdfReader(str(source)))
    writer.encrypt(password)
    with target.open("wb") as stream:
        writer.write(stream)


def test_an_encrypted_pdf_is_named_instead_of_read_as_a_scan(tmp_path):
    pytest.importorskip("pypdf")
    plain = tmp_path / "clair.pdf"
    plain.write_bytes(build_pdf("Contrat"))
    locked = tmp_path / "verrouille.pdf"
    encrypted_pdf(plain, locked)

    produced, info = pdfreader.rows(locked)

    assert produced == [] and info["status"] == "encrypted"


def test_a_truncated_pdf_is_unreadable_rather_than_a_scan(tmp_path):
    pytest.importorskip("pypdf")
    path = tmp_path / "tronque.pdf"
    path.write_bytes(build_pdf("Contrat")[:120])

    produced, info = pdfreader.rows(path)

    assert produced == [] and info["status"] == "unreadable" and info["warnings"]


def test_an_empty_file_is_not_a_pdf(tmp_path):
    pytest.importorskip("pypdf")
    path = tmp_path / "vide.pdf"
    path.write_bytes(b"")

    produced, info = pdfreader.rows(path)

    assert produced == [] and info["status"] in ("unreadable", "empty")
