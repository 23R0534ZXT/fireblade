"""A case does not end at its folder: its packages, its archive and its annex go too."""
import csv

import pytest

from fireblade.core.case_destruction import destroy_case, outside_entries
from fireblade.core.investigations import InvestigationLibrary
from fireblade.web.service import Library


def _case(root, name="Residue case"):
    library = InvestigationLibrary(root)
    data = library.create(name, "", "windows")
    folder = library.folder(data["id"])
    (folder/"notes.txt").write_text("evidence copy", encoding="utf-8")
    return data["id"], folder


def _library_with_residue(tmp_path):
    root = tmp_path/"cases"
    root.mkdir()
    identifier, folder = _case(root)
    prefix = identifier[:8]
    (root/"exports").mkdir()
    (root/"archives").mkdir()
    (root/"certificates").mkdir()
    package = root/"exports"/f"{prefix}.fireblade"
    package.write_text("portable package", encoding="utf-8")
    other = root/"exports"/"deadbeef.fireblade"
    other.write_text("another case", encoding="utf-8")
    archive = root/"archives"/f"{prefix}.fireblade-archive.zip"
    archive.write_text("archive", encoding="utf-8")
    annex = root/"certificates"/f"annex-{prefix}"/"destruction"
    annex.mkdir(parents=True)
    (annex/"photo.jpg").write_bytes(b"\xff\xd8\xff")
    return root, identifier, folder, package, archive, annex, other


def test_only_the_case_prefix_is_claimed(tmp_path):
    root, identifier, _folder, package, archive, annex, other = _library_with_residue(tmp_path)
    found = outside_entries(root, identifier)
    assert package in found and archive in found
    assert annex.parent in found
    assert other not in found
    # A short or empty identifier never matches: it would claim the library.
    assert outside_entries(root, "") == []
    assert outside_entries(root, identifier[:4]) == []


def test_destroying_a_case_destroys_what_it_left_outside(tmp_path):
    root, identifier, folder, package, archive, annex, other = _library_with_residue(tmp_path)
    certificate = root/"certificates"/"pv.html"
    record = destroy_case(folder, "dod3", certificate_path=certificate,
                          case_name="Residue case", case_id=identifier,
                          extras=[str(path) for path in outside_entries(root, identifier)])
    assert not folder.exists()
    assert not package.exists() and not archive.exists() and not annex.exists()
    assert other.exists(), "another case's package must survive"
    assert certificate.is_file()
    assert record["outside"] == 3
    assert record["folder_removed"] is True
    # The record names the outside files as such, so the certificate can say it.
    assert all(item.get("outside") for item in record["files"][:3])
    assert (root/"exports").is_dir() and (root/"archives").is_dir()


def test_the_service_reports_residue_before_destroying(tmp_path):
    root, identifier, folder, package, archive, annex, other = _library_with_residue(tmp_path)
    service = Library(root)
    before = service.residue(identifier)
    assert before["files"] == 3
    assert {item["folder"] for item in before["items"]} == {"exports", "archives", "certificates"}

    result = service.destroy(identifier, "dod3", operator="Tester",
                             confirmation="Residue case")
    assert result["outside"] == 3
    assert not folder.exists() and not package.exists() and not archive.exists()
    assert other.exists()
    with pytest.raises(OSError):
        # Nothing is left to report: the case folder is gone.
        service.residue(identifier)
