"""Nothing a collection holds is left unread: what no reader owns is read as what it is."""

import json
import sqlite3
import struct

from fireblade.core import generic_files
from fireblade.core.investigations import InvestigationLibrary
from fireblade.web.service import Library


def _pe(path, extra=b""):
    data = bytearray(512)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\x00\x00"
    struct.pack_into("<HHI", data, 0x84, 0x8664, 3, 1700000000)
    struct.pack_into("<H", data, 0x84 + 16, 240)
    struct.pack_into("<H", data, 0x98, 0x20B)
    struct.pack_into("<H", data, 0x98 + 68, 3)
    path.write_bytes(bytes(data) + extra)


def test_a_pe_header_is_read_without_running_anything(tmp_path):
    _pe(tmp_path / "a.dll")
    row = generic_files.inventory_row(tmp_path / "a.dll")
    assert row["Machine"] == "x64" and row["Subsystem"] == "Windows console"
    assert row["Compiled (UTC)"].startswith("2023-11-14")
    assert len(row["SHA-256"]) == 64 and row["Type"] == "PE executable or library"


def test_every_kind_of_unowned_file_is_read_and_accounted_for(tmp_path):
    folder = tmp_path / "collector"
    (folder / "Processes").mkdir(parents=True)
    (folder / "Browser").mkdir()
    _pe(folder / "Processes" / "a.dll")
    _pe(folder / "Processes" / "b.exe", b"x")
    (folder / "Processes" / "blob.bin").write_bytes(b"\x00\x01" * 64)
    connection = sqlite3.connect(folder / "Browser" / "unknown.sqlite")
    connection.execute("create table visits(url, at)")
    connection.execute("insert into visits values('http://a', 1)")
    connection.commit()
    connection.close()
    (folder / "Browser" / "prefs.json").write_text(json.dumps({"a": {"b": 1}}))
    (folder / "notes.txt").write_text("one\ntwo\n")
    root = tmp_path / "cases"
    root.mkdir()
    library = Library(root)
    identifier = InvestigationLibrary(root).create("Collector", "", "windows")["id"]
    library.import_source(identifier, folder, organization="files")
    files = library.imports(identifier)["collections"][0]["files"]
    by_name = {item["name"]: item for item in files}
    assert not [item for item in files if item["status"] == "unsupported"], files
    assert by_name["a.dll"]["status"] == "complete" and "inventory" in by_name["a.dll"]["reason"]
    assert by_name["unknown.sqlite"]["status"] == "complete"
    labels = {item["label"] for item in library.case(identifier)["analyses"]}
    assert {"Files inventory.csv", "notes.txt", "prefs.json"} <= labels
    assert "unknown.sqlite" in labels, labels  # its tables are the analysis
    library.close()
