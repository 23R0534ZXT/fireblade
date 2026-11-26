"""An import checks the disk before it starts, and keeps what it wrote when it is cut short."""

import errno
import shutil
from types import SimpleNamespace

import pytest

from fireblade.core.collection import Collection
from fireblade.core.investigations import InvestigationLibrary
from fireblade.web.service import Library, ServiceError


@pytest.fixture()
def lib(tmp_path):
    root = tmp_path / "cases"
    root.mkdir()
    library = Library(root)
    identifier = InvestigationLibrary(root).create("Room", "", "windows")["id"]
    return library, identifier, tmp_path


def _evidence(folder, files=3):
    folder.mkdir()
    for number in range(files):
        (folder / f"f{number}.csv").write_text(
            "Time,Host,User\n"
            + "".join(f"2026-11-01T10:0{i}:00Z,PC{i},u{number}{i}\n" for i in range(5))
        )
    return folder


def test_an_import_that_cannot_fit_is_refused_with_the_figures(lib, monkeypatch):
    library, identifier, tmp_path = lib
    source = _evidence(tmp_path / "evidence")
    monkeypatch.setattr(
        shutil, "disk_usage", lambda _path: SimpleNamespace(total=10**9, used=10**9, free=1000)
    )
    with pytest.raises(ServiceError) as refused:
        library.start_import_job(identifier, str(source))
    text = str(refused.value)
    assert "Not enough free disk space" in text and "Nothing was imported" in text
    assert "3 file(s)" in text and "free" in text


def test_a_tight_disk_starts_and_says_so_in_the_log(lib, monkeypatch):
    library, identifier, tmp_path = lib
    source = _evidence(tmp_path / "evidence")
    size = sum(item.stat().st_size for item in source.iterdir())
    free = int(size * 2) + library.SPACE_MARGIN + 1  # above the floor, below the comfort level
    monkeypatch.setattr(
        shutil, "disk_usage", lambda _path: SimpleNamespace(total=10**9, used=0, free=free)
    )
    started = library.start_import_job(identifier, str(source))
    with library._lock:
        log = list(library._jobs[started["job"]]["log"])
    assert log and log[0].startswith("Low disk space")


def test_a_roomy_disk_is_not_in_the_way(lib):
    library, identifier, tmp_path = lib
    info = library.check_room(identifier, _evidence(tmp_path / "evidence"))
    assert info["status"] == "ok" and info["files"] == 3


def test_what_was_written_before_the_disk_filled_is_kept_and_said(lib, monkeypatch):
    library, identifier, tmp_path = lib
    source = _evidence(tmp_path / "evidence")

    def full(self, *_args, **_kwargs):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(Collection, "verify_documents", full)
    result = library.import_source(identifier, source, organization="files")
    assert result["status"] == "interrupted" and result["analyses"] == 3
    assert "the disk is full" in result["message"] and "3 analysis(es)" in result["message"]
    assert len(library.case(identifier)["analyses"]) == 3, "they are listed in the case"


def test_a_failure_before_anything_was_written_says_nothing_was_imported(lib, monkeypatch):
    library, identifier, tmp_path = lib
    source = _evidence(tmp_path / "evidence")

    def full(self, *_args, **_kwargs):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(Collection, "inventorize", full)
    with pytest.raises(ServiceError) as failed:
        library.import_source(identifier, source, organization="files")
    assert "the disk is full" in str(failed.value)
    assert "Nothing was imported" in str(failed.value)
