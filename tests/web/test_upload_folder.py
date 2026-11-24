"""A folder sent from the browser keeps its tree; a path that tries to leave is refused."""

import io

import pytest
from fastapi import HTTPException

from fireblade.web.server import _store_upload


class _Sent:
    """The part of an UploadFile this function reads."""

    def __init__(self, name, data=b"bytes"):
        self.filename = name
        self.file = io.BytesIO(data)


def test_a_folder_upload_rebuilds_the_path_inside_evidence(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    target = _store_upload(case, _Sent("a.evtx", b"one"), relative="Collection/C/Windows/a.evtx")
    assert target == case / "evidence" / "Collection" / "C" / "Windows" / "a.evtx"
    assert target.read_bytes() == b"one"


def test_a_relative_path_may_not_leave_the_case(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    with pytest.raises(HTTPException):
        _store_upload(case, _Sent("passwd"), relative="../../etc/passwd")
    with pytest.raises(HTTPException):
        _store_upload(case, _Sent("x"), relative="..")
    assert not (case / "evidence").exists() or not any((case / "evidence").iterdir())


def test_a_plain_upload_still_gets_a_free_name(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    (case / "evidence").mkdir()
    (case / "evidence" / "a.csv").write_bytes(b"old")
    target = _store_upload(case, _Sent("a.csv", b"new"))
    assert target.name == "a-2.csv"
    assert (case / "evidence" / "a.csv").read_bytes() == b"old"
