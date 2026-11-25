"""Archives in a folder: opened, nested ones too, and never at the evidence's expense."""

import gzip
import io
import tarfile
import zipfile

from fireblade.core import archives
from fireblade.core.investigations import InvestigationLibrary
from fireblade.web.service import Library

AUTH = b"Nov  1 10:00:01 srv sshd[1]: Failed password for root from 10.0.0.9 port 22 ssh2\n"


def _tar(members):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tarred:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tarred.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def test_a_folder_with_zips_tars_and_nested_archives_is_read_whole(tmp_path):
    folder = tmp_path / "var" / "log"
    (folder / "sub" / "deeper").mkdir(parents=True)
    (folder / "auth.log").write_bytes(AUTH)
    (folder / "sub" / "syslog.1.gz").write_bytes(
        gzip.compress(b"Oct 31 09:00:00 srv kernel: old\n")
    )
    inner = _tar({"inner/messages": b"Nov  2 11:00:00 srv app[9]: in a tar in a zip\n"})
    with zipfile.ZipFile(folder / "sub" / "deeper" / "bundle.zip", "w") as bundle:
        bundle.writestr("nested.tar", inner)
        bundle.writestr("plain/dmesg", "Nov  3 12:00:00 srv kernel: in a zip\n")
    (folder / "old.tar.gz").write_bytes(
        gzip.compress(_tar({"kern.log": b"Nov  4 13:00:00 srv kernel: in a tgz\n"}))
    )
    root = tmp_path / "cases"
    root.mkdir()
    library = Library(root)
    identifier = InvestigationLibrary(root).create("Archives", "", "linux")["id"]
    result = library.import_source(identifier, folder, organization="files")
    labels = [item["label"] for item in library.case(identifier)["analyses"]]
    assert {"auth.log", "syslog.1.gz", "dmesg", "messages", "kern.log"} <= set(labels), labels
    listing = library.imports(identifier)["collections"][0]["files"]
    names = [item["name"] for item in listing]
    assert any(name.endswith("bundle.zip!/nested.tar") for name in names), names
    assert result["analyses"] == 5
    # the evidence folder was not written to
    assert sorted(path.name for path in folder.rglob("*") if path.is_file()) == sorted(
        ["auth.log", "syslog.1.gz", "bundle.zip", "old.tar.gz"]
    )
    library.close()


def test_a_member_that_climbs_out_or_is_a_link_is_refused_and_reported(tmp_path):
    bad = tmp_path / "bad.tar"
    with tarfile.open(bad, "w") as tarred:
        data = b"x"
        info = tarfile.TarInfo("../escape.txt")
        info.size = 1
        tarred.addfile(info, io.BytesIO(data))
        link = tarfile.TarInfo("link")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        tarred.addfile(link)
        good = tarfile.TarInfo("ok.log")
        good.size = 1
        tarred.addfile(good, io.BytesIO(b"y"))
    files, problems = archives.extract(bad, tmp_path / "out")
    assert [path.name for path in files] == ["ok.log"]
    assert len(problems) == 2 and not (tmp_path / "escape.txt").exists()


def test_a_spreadsheet_is_not_opened_as_an_archive(tmp_path):
    book = tmp_path / "sheet.xlsx"
    with zipfile.ZipFile(book, "w") as bundle:
        bundle.writestr("a.xml", "<x/>")
    assert not archives.is_archive(book)
