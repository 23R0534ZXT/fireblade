"""The destruction certificate goes where the analyst says, and never inside the case."""
from pathlib import Path

import pytest

from fireblade.core.investigations import InvestigationLibrary
from fireblade.web.service import Library, ServiceError


def _case(tmp_path):
    root = tmp_path/"cases"
    root.mkdir()
    library = InvestigationLibrary(root)
    data = library.create("Certificate case")
    folder = library.folder(data["id"])
    (folder/"notes.txt").write_text("evidence", encoding="utf-8")
    return root, data["id"], folder


def test_the_certificate_lands_in_the_folder_the_analyst_names(tmp_path):
    root, identifier, folder = _case(tmp_path)
    service = Library(root)
    destination = tmp_path/"pv"
    result = service.destroy(identifier, "dod3", confirmation="Certificate case",
                             certificate_folder=str(destination))
    written = Path(result["certificate"])
    assert written.parent == destination
    assert written.is_file() and written.suffix == ".html"
    assert not folder.exists(), "the case still went"


def test_the_default_folder_is_the_librarys_own(tmp_path):
    root, identifier, folder = _case(tmp_path)
    service = Library(root)
    result = service.destroy(identifier, "dod3", confirmation="Certificate case")
    assert Path(result["certificate"]).parent == (root/"certificates").resolve()


def test_a_certificate_inside_the_case_is_refused(tmp_path):
    root, identifier, folder = _case(tmp_path)
    service = Library(root)
    with pytest.raises(ServiceError):
        service.destroy(identifier, "dod3", confirmation="Certificate case",
                        certificate_folder=str(folder/"certificates"))
    assert folder.exists(), "nothing was destroyed"


def test_a_relative_folder_is_refused(tmp_path):
    root, identifier, folder = _case(tmp_path)
    service = Library(root)
    with pytest.raises(ServiceError):
        service.destroy(identifier, "dod3", confirmation="Certificate case",
                        certificate_folder="pv")
    assert folder.exists()
