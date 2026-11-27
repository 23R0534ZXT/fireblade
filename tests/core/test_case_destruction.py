"""Destroying a case: every file overwritten, the folder removed, the certificate outside."""

import json
import os

import pytest

from fireblade.core import case_destruction, destruction


def make_case(tmp_path, name="CASE-1"):
    folder = tmp_path / "Cases" / name
    (folder / "analyses").mkdir(parents=True)
    (folder / "evidence").mkdir()
    (folder / "case.json").write_text(
        json.dumps(dict(id=name, name="Affaire test")), encoding="utf-8"
    )
    (folder / "workspace.json").write_text(json.dumps(dict(actions=[])), encoding="utf-8")
    (folder / "analyses" / "a.timeline").write_bytes(b"timeline-data" * 100)
    (folder / "evidence" / "poste.bin").write_bytes(b"EVTX" * 500)
    (folder / "session-1.fireblade-session").write_text("{}", encoding="utf-8")
    return folder


def test_collect_lists_every_file_of_the_case(tmp_path):
    folder = make_case(tmp_path)
    files, folders, links = case_destruction.collect(folder)
    names = {item["relative"] for item in files}
    assert names == {
        "case.json",
        "workspace.json",
        "analyses/a.timeline",
        "evidence/poste.bin",
        "session-1.fireblade-session",
    }
    assert links == [] and len(folders) == 3


def test_a_folder_that_is_not_a_case_is_refused(tmp_path):
    folder = tmp_path / "random"
    folder.mkdir()
    (folder / "notes.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="case Fireblade"):
        case_destruction.collect(folder)


def test_the_whole_case_disappears_and_the_certificate_is_written_outside(tmp_path):
    folder = make_case(tmp_path)
    certificate = tmp_path / "PV" / "destruction.pdf"
    certificate.parent.mkdir()
    record = case_destruction.destroy_case(
        folder,
        "dod3",
        operator="Analyste",
        witness="Témoin",
        reason="Clôture",
        certificate_path=certificate,
        case_name="Affaire test",
        case_id="CASE-1",
    )
    assert not folder.exists(), "the case folder survived"
    assert certificate.is_file()
    assert record["folder_removed"] is True
    assert record["scope"] == "case"
    assert len(record["files"]) == 5
    assert all(item["deleted"] for item in record["files"])
    assert all(item.get("sha256_before") for item in record["files"])


def test_a_certificate_inside_the_case_is_refused(tmp_path):
    folder = make_case(tmp_path)
    with pytest.raises(ValueError, match="hors du case"):
        case_destruction.destroy_case(folder, "dod3", certificate_path=folder / "pv.pdf")


def test_the_record_names_every_relative_path(tmp_path):
    folder = make_case(tmp_path)
    certificate = tmp_path / "pv.html"
    record = case_destruction.destroy_case(folder, "dod7", certificate_path=certificate)
    relatives = {item["relative"] for item in record["files"]}
    assert "analyses/a.timeline" in relatives
    assert "evidence/poste.bin" in relatives
    assert certificate.is_file()
    assert certificate.read_text(encoding="utf-8").count("<") > 0


def test_the_certificate_keeps_its_table_readable_and_hashes_complete(tmp_path):
    folder = make_case(tmp_path)
    certificate = tmp_path / "pv.html"
    record = case_destruction.destroy_case(folder, "dod3", certificate_path=certificate)
    html = certificate.read_text(encoding="utf-8")
    assert "Empreintes complètes" in html
    digest = record["files"][0]["sha256_before"]
    assert digest in html, "the full hash is missing from the appendix"
    # The summary table stays one line per file; the digests live in the appendix.
    table = html.split("<h2>2. Empreintes complètes</h2>")[0]
    assert digest not in table, "a 64-character hash is back in the summary table"
    assert digest[:12] + "…" + digest[-6:] not in table


def test_quick_erasure_does_not_read_or_overwrite_file_contents(tmp_path, monkeypatch):
    folder = make_case(tmp_path)
    source = folder / "evidence" / "poste.bin"
    surviving_link = tmp_path / "original.bin"
    os.link(source, surviving_link)

    def reject_content_io(*_args):
        pytest.fail("Quick erase must not fingerprint or overwrite files")

    monkeypatch.setattr(destruction, "sha256_file", reject_content_io)
    monkeypatch.setattr(destruction, "_write_pass", reject_content_io)
    record = case_destruction.destroy_case(folder, "quick", certificate_path=tmp_path / "pv.html")

    assert record["folder_removed"]
    assert record["passes"] == 0
    assert all(item["deleted"] and not item["verified"] for item in record["files"])
    assert surviving_link.read_bytes() == b"EVTX" * 500
