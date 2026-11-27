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


def test_a_catscale_family_is_named_in_english_everywhere_it_shows(tmp_path):
    """The Artifact cell, the timeline source and the reasons of an engine that is missing."""
    folder = tmp_path / "node-20261102-1000" / "Process_and_Network"
    folder.mkdir(parents=True)
    (folder / "node-20261102-1000-processes-ef.txt").write_text(
        "UID PID PPID C STIME TTY TIME CMD\nroot 42 1 0 08:00 ? 00:01 /bin/sh -c id\n"
    )
    root = tmp_path / "cases"
    root.mkdir()
    library = Library(root)
    identifier = InvestigationLibrary(root).create("Linux", "", "linux")["id"]
    library.import_source(identifier, tmp_path / "node-20261102-1000", organization="artifacts")
    analyses = library.case(identifier)["analyses"]
    users = next(item for item in analyses if item["label"] == "Processes and network")
    page = library.rows(identifier, users["index"], limit=5)
    artifact = page["columns"].index("Artifact")
    assert page["rows"][0][artifact] == "Processes and network", page["rows"][0]
    names = [item["name"] for item in library.timeline(identifier)["sources"]]
    assert "Processes and network.csv" in names and not [n for n in names if "Processus" in n], (
        names
    )
    library.close()


def test_the_reasons_of_a_file_read_by_two_missing_engines_are_in_english():
    from fireblade.web.service import _english

    french = (
        "Moteur intégré absent : A. La construction du pack forensic est nécessaire. ; "
        "Moteur intégré absent : B. La construction du pack forensic est nécessaire."
    )
    assert "intégré" not in _english(french) and _english(french).count("Built-in engine") == 2


def test_generic_sqlite_reader_includes_committed_wal_without_changing_evidence(tmp_path):
    import csv
    import shutil

    live = tmp_path / "live.sqlite"
    connection = sqlite3.connect(live)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE evidence (Id INTEGER, Marker TEXT)")
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("INSERT INTO evidence VALUES (1, 'committed-only-in-wal')")
        connection.commit()
        source = tmp_path / "collected.sqlite"
        shutil.copyfile(live, source)
        wal = source.with_name(source.name + "-wal")
        shutil.copyfile(live.with_name(live.name + "-wal"), wal)
    finally:
        connection.close()
    before = {path: path.read_bytes() for path in [source, wal]}
    output = tmp_path / "output"
    output.mkdir()
    result = generic_files.parse(source, output)
    assert sum(table["rows"] for table in result["outputs"]) == 1
    with open(result["outputs"][0]["csv"], newline="") as stream:
        assert list(csv.reader(stream)) == [["Id", "Marker"], ["1", "committed-only-in-wal"]]
    assert all(path.read_bytes() == data for path, data in before.items())
    assert not source.with_name(source.name + "-shm").exists()
    assert not list(output.glob("sqlite-work-*"))
