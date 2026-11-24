"""Reading a file the collection could not identify, on the examiner's decision."""

import json
from pathlib import Path

import pytest

from fireblade.core.collection import Collection, ToolPack, sha256


@pytest.fixture
def collection(tmp_path):
    root = tmp_path / "evidence"
    root.mkdir()
    (root / "note.txt").write_text("Réunion du 14/11/2026 09:30\nligne deux\n", encoding="utf-8")
    (root / "page.dat").write_text(
        "<!doctype html><html><body><p>Preuve visible</p>"
        '<a href="https://exemple.fr/a">lien</a></body></html>',
        encoding="utf-8",
    )
    (root / "export.dat").write_text("Utilisateur,Valeur\nalice,001\n", encoding="utf-8")
    (root / "blob.bin").write_bytes(bytes(range(256)))
    return Collection(root, tmp_path / "work", ToolPack(tmp_path / "pack"))


def entries(report):
    return {Path(entry["path"]).name: entry for entry in report["files"]}


def test_nothing_is_read_until_the_examiner_asks(collection):
    report = collection.parse()
    names = entries(report)
    assert names["note.txt"]["status"] == "unsupported"
    assert names["page.dat"]["status"] == "unsupported"
    assert report["documents"] == []


def test_a_text_file_read_on_request_becomes_an_analysis(collection):
    report = collection.parse()
    entry = entries(report)["note.txt"]
    before = sha256(entry["path"])

    entry = collection.analyse_single(entry["path"], "text")

    assert entry["status"] == "complete"
    assert entry["tools"] == ["TextReader"]
    run = entry["runs"][-1]
    assert run["reader"] == "text" and run["status"] == "complete"
    output = run["outputs"][0]
    assert Path(output["csv"]).is_file() and Path(output["analysis"]).is_file()
    assert len(collection.report["documents"]) == 1
    assert sha256(entry["path"]) == before, "la preuve ne doit jamais être modifiée"


def test_the_request_and_its_result_survive_a_reopen(collection):
    collection.parse()
    entry = entries(collection.report)["note.txt"]
    collection.analyse_single(entry["path"], "text")

    saved = json.loads((collection.output / "collection.json").read_text(encoding="utf-8"))
    reopened = entries(saved)["note.txt"]
    assert reopened["status"] == "complete" and reopened["tools"] == ["TextReader"]
    assert reopened["sha256"] == entry["sha256"]

    again = Collection.reopen(collection.output, collection.pack)
    assert entries(again.report)["note.txt"]["runs"][-1]["reader"] == "text"


def test_a_saved_page_gives_its_text_and_its_links(collection):
    collection.parse()
    entry = entries(collection.report)["page.dat"]

    entry = collection.analyse_single(entry["path"], "html")

    assert entry["status"] == "complete" and entry["tools"] == ["HTMLPage"]
    text = Path(entry["runs"][-1]["outputs"][0]["csv"]).read_text(encoding="utf-8")
    assert "Preuve visible" in text and "https://exemple.fr/a" in text


def test_reading_the_same_file_twice_keeps_both_reads(collection):
    collection.parse()
    entry = entries(collection.report)["page.dat"]

    collection.analyse_single(entry["path"], "text")
    entry = collection.analyse_single(entry["path"], "html")

    assert entry["status"] == "complete"
    assert entry["tools"] == ["HTMLPage", "TextReader"], "chaque lecture garde son nom"
    assert [run["reader"] for run in entry["runs"]] == ["text", "html"]
    assert len(entry["runs"][0]["outputs"]) == len(entry["runs"][1]["outputs"]) == 1
    assert len(collection.report["documents"]) == 2


def test_a_binary_file_cannot_be_forced_into_text(collection):
    collection.parse()
    entry = entries(collection.report)["blob.bin"]

    entry = collection.analyse_single(entry["path"], "text")

    assert entry["status"] == "error"
    assert "Aucune ligne lisible" in entry["error"]
    assert entry["runs"][-1]["outputs"] == []
    assert collection.report["documents"] == []


def test_a_file_changed_since_its_recorded_hash_is_refused(collection):
    collection.parse()
    entry = entries(collection.report)["note.txt"]
    # The collection has no hash for a file it did not read: the first read fixes it.
    collection.analyse_single(entry["path"], "text")
    Path(entry["path"]).write_text("contenu remplacé\n", encoding="utf-8")

    with pytest.raises(ValueError, match="a changé depuis la collecte"):
        collection.analyse_single(entry["path"], "text")


def test_an_unknown_reader_is_refused_before_anything_is_touched(collection):
    collection.parse()
    entry = entries(collection.report)["note.txt"]

    with pytest.raises(ValueError, match="Lecteur inconnu"):
        collection.analyse_single(entry["path"], "ocr")


def test_a_table_can_be_imported_even_without_a_csv_suffix(collection):
    collection.parse()
    entry = entries(collection.report)["export.dat"]

    entry = collection.analyse_single(entry["path"], "csv")

    assert entry["status"] == "complete" and entry["tools"] == ["native"]
    assert len(collection.report["documents"]) == 1


def test_a_file_the_collection_never_saw_still_gets_a_line_in_the_report(collection):
    collection.parse()
    late = collection.root / "ajoutée après la collecte.txt"
    late.write_text("arrivée plus tard\n", encoding="utf-8")

    entry = collection.analyse_single(late, "text")

    assert entry["status"] == "complete"
    assert entries(collection.report)["ajoutée après la collecte.txt"] is entry


def test_a_pdf_read_on_request_becomes_an_analysis(collection):
    pytest.importorskip("pypdf")
    from pdf_sample import build_pdf

    collection.parse()
    document = collection.root / "contrat.pdf"
    document.write_bytes(build_pdf("Signé le 14/11/2026 par la direction"))

    entry = collection.analyse_single(document, "pdf")

    assert entry["status"] == "complete" and entry["tools"] == ["PDFReader"]
    assert Path(entry["runs"][-1]["outputs"][0]["analysis"]).is_file()


def test_a_scanned_pdf_is_reported_rather_than_read_invented(collection):
    pytest.importorskip("pypdf")
    from pdf_sample import build_pdf

    collection.parse()
    scan = collection.root / "scan.pdf"
    scan.write_bytes(build_pdf(None))

    entry = collection.analyse_single(scan, "pdf")

    assert entry["status"] == "no_output"
    assert "sans couche texte" in entry["error"]
    assert collection.report["documents"] == []


def test_a_pdf_without_the_extension_is_refused_before_reading(collection, monkeypatch):
    from fireblade.core import pdfreader

    monkeypatch.setattr(pdfreader, "backend", lambda: None)
    collection.parse()
    document = collection.root / "facture.pdf"
    document.write_bytes(b"%PDF-1.4\n")

    entry = collection.analyse_single(document, "pdf")

    assert entry["status"] == "error" and "pypdf" in entry["error"]


def test_a_text_file_read_in_part_is_a_warning_not_a_silent_analysis(collection, monkeypatch):
    from fireblade.core import textreader

    collection.parse()
    document = collection.root / "journal.txt"
    document.write_text(
        "2026-11-14 08:00 première ligne\n2026-11-14 09:00 seconde ligne\n", encoding="utf-8"
    )
    monkeypatch.setattr(textreader, "LIMIT_BYTES", 30)

    entry = collection.analyse_single(document, "text")

    assert entry["status"] == "attention"
    run = entry["runs"][-1]
    assert run["status"] == "complete_with_warnings"
    assert run["textreader"]["truncated"] is True
    assert run["warnings"], "une lecture partielle doit être dite, pas silencieuse"
    assert Path(run["outputs"][0]["analysis"]).is_file()


def test_an_encrypted_pdf_is_reported_with_its_reason(collection):
    pypdf = pytest.importorskip("pypdf")
    from pdf_sample import build_pdf

    collection.parse()
    plain = collection.root / "clair.pdf"
    plain.write_bytes(build_pdf("Contrat signé"))
    locked = collection.root / "verrouille.pdf"
    writer = pypdf.PdfWriter()
    writer.append(pypdf.PdfReader(str(plain)))
    writer.encrypt("mot-de-passe")
    with locked.open("wb") as stream:
        writer.write(stream)

    entry = collection.analyse_single(locked, "pdf")

    assert entry["status"] == "no_output" and "chiffré" in entry["error"]
    assert collection.report["documents"] == []


def test_an_import_that_runs_out_of_memory_is_retried_with_more(collection, monkeypatch):
    import duckdb

    budgets = []
    original = Collection._import_once

    def once(self, csv, kind, view, register, budget, evidence=None):
        budgets.append(getattr(budget, "memory_mb", None))
        if len(budgets) == 1:
            raise duckdb.OutOfMemoryException("Out of Memory Error: failed to pin block")
        return original(self, csv, kind, view, register, budget, evidence)

    monkeypatch.setattr(Collection, "_import_once", once)
    source = collection.root / "note.txt"
    source.write_bytes("une ligne\n".encode("utf-8"))

    document = collection.import_result(str(source), "native", register=False)

    assert len(budgets) == 2, "un second essai, pas trois"
    assert budgets[1] and budgets[1] >= 512, "le second essai demande plus de mémoire"
    assert Path(document["path"]).is_file()
