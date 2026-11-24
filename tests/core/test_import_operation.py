"""One import operation: mixed sources, duplicates, resume, isolation, journal, proof.

The promise this file pins is the one the product makes: no file disappears without
a row, one bad file does not cost the operation, and what was written is counted
again before the report calls it read.
"""

import json
import threading
from pathlib import Path

import duckdb

from fireblade.core.collection import Collection, ToolPack, verify_analysis
from fireblade.core.errors import cancellation_scope
from fireblade.core.import_journal import (
    ImportJournal,
)
from fireblade.core.import_journal import (
    read as read_journal,
)
from fireblade.core.import_journal import (
    summary as journal_summary,
)
from fireblade.core.settings import Settings


def build_pack(tmp_path):
    pack = tmp_path / "pack"
    (pack / "dotnet").mkdir(parents=True)
    (pack / "dotnet" / "dotnet.exe").touch()
    return ToolPack(pack)


def write_csv(path, rows=2, header="User,Value", tag=None):
    """Distinct content per file: two files with one body are a duplicate, by design."""
    path = Path(path)
    tag = tag or path.name
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"{tag}-{index},{index:03d}" for index in range(rows))
    path.write_text(header + "\n" + body + "\n", encoding="utf-8", newline="")
    return path


def rows_of(report):
    return {Path(entry["path"]).name: entry for entry in report["files"]}


def test_one_operation_reads_files_and_folders_together(tmp_path):
    """A folder, another folder and a loose file are one operation, one report."""
    disk = tmp_path / "disk"
    write_csv(disk / "a.csv")
    write_csv(disk / "sub" / "b.csv")
    extra = tmp_path / "extra"
    write_csv(extra / "c.csv")
    single = write_csv(tmp_path / "d.csv")
    collection = Collection(
        [disk, extra, single], tmp_path / "work", build_pack(tmp_path), settings=Settings(threads=1)
    )
    report = collection.parse()
    assert report["status"] == "complete"
    assert sorted(rows_of(report)) == ["a.csv", "b.csv", "c.csv", "d.csv"]
    assert [entry["status"] for entry in report["files"]] == ["complete"] * 4
    assert len(report["documents"]) == 4
    assert len(report["sources"]) == 3


def test_a_file_that_no_reader_knows_still_gets_a_row(tmp_path):
    folder = tmp_path / "disk"
    write_csv(folder / "a.csv")
    (folder / "ghost.bin").write_bytes(b"\x00\x01opaque")
    report = Collection(
        folder, tmp_path / "work", build_pack(tmp_path), settings=Settings(threads=1)
    ).parse()
    assert rows_of(report)["ghost.bin"]["status"] == "unsupported"
    assert rows_of(report)["a.csv"]["status"] == "complete"


def test_identical_content_is_read_once_and_the_copy_is_named(tmp_path):
    folder = tmp_path / "disk"
    write_csv(folder / "a.csv")
    (folder / "copy.csv").write_bytes((folder / "a.csv").read_bytes())
    report = Collection(
        folder, tmp_path / "work", build_pack(tmp_path), settings=Settings(threads=1)
    ).parse()
    rows = rows_of(report)
    assert rows["a.csv"]["status"] == "complete"
    assert rows["copy.csv"]["status"] == "duplicate"
    assert rows["copy.csv"]["duplicate_of"] == str(folder / "a.csv")
    assert "Same content as" in rows["copy.csv"]["reason"]
    # The point of the check: one tab, not two readings of one piece of evidence.
    assert len(report["documents"]) == 1


def test_a_second_import_refuses_what_the_case_already_read(tmp_path):
    folder = tmp_path / "disk"
    write_csv(folder / "a.csv")
    collected = tmp_path / "Collectes"
    collected.mkdir()
    pack = build_pack(tmp_path)
    Collection(
        folder, collected / "first", pack, settings=Settings(threads=1), index_folder=collected
    ).parse()
    report = Collection(
        folder, collected / "second", pack, settings=Settings(threads=1), index_folder=collected
    ).parse()
    entry = report["files"][0]
    assert entry["status"] == "duplicate"
    assert "Already imported from" in entry["reason"]
    assert entry["duplicate_of"] == str(folder / "a.csv")
    assert report["documents"] == []
    # The record closes itself, even when the index was written after the files.
    kinds = [event["kind"] for event in read_journal(collected / "second" / "journal.jsonl")]
    assert kinds[-1] == "operation.finished" and "index.updated" in kinds


def test_a_reader_that_raises_costs_one_row_not_the_operation(tmp_path, monkeypatch):
    folder = tmp_path / "disk"
    for name in ("a.csv", "b.csv", "c.csv"):
        write_csv(folder / name)
    original = Collection._read_entry

    def explode(self, source, entry):
        if Path(source).name == "b.csv":
            raise RuntimeError("reader exploded")
        return original(self, source, entry)

    monkeypatch.setattr(Collection, "_read_entry", explode)
    report = Collection(
        folder, tmp_path / "work", build_pack(tmp_path), settings=Settings(threads=1)
    ).parse()
    rows = rows_of(report)
    assert rows["b.csv"]["status"] == "error"
    assert rows["b.csv"]["reason"] == "reader exploded"
    assert rows["a.csv"]["status"] == "complete" and rows["c.csv"]["status"] == "complete"
    assert len(report["documents"]) == 2
    assert report["status"] == "complete"


def test_resume_reads_what_was_left_and_keeps_what_was_done(tmp_path):
    folder = tmp_path / "disk"
    for name in ("a.csv", "b.csv", "c.csv"):
        write_csv(folder / name)
    stop = threading.Event()
    seen = []

    def progress(message):
        if message.startswith("Collecte"):
            seen.append(message)
            if len(seen) >= 2:
                stop.set()

    collection = Collection(
        folder,
        tmp_path / "work",
        build_pack(tmp_path),
        settings=Settings(threads=1),
        progress=progress,
    )
    with cancellation_scope(stop):
        report = collection.parse()
    assert report["status"] == "cancelled"
    done = [Path(entry["path"]).name for entry in report["files"] if entry["status"] == "complete"]
    assert len(done) == 1
    assert collection.resumable() == 2

    report = collection.resume()
    assert report["status"] == "complete"
    assert [entry["status"] for entry in report["files"]] == ["complete"] * 3
    assert len(report["documents"]) == 3
    kinds = [event["kind"] for event in read_journal(collection.output / "journal.jsonl")]
    assert "resumed" in kinds
    finished = [
        event
        for event in read_journal(collection.output / "journal.jsonl")
        if event["kind"] == "operation.finished"
    ]
    assert finished[-1]["resumed"] is True and finished[-1]["reread"] == 2


def test_resume_rereads_a_row_whose_analysis_disappeared(tmp_path):
    folder = tmp_path / "disk"
    write_csv(folder / "a.csv")
    collection = Collection(
        folder, tmp_path / "work", build_pack(tmp_path), settings=Settings(threads=1)
    )
    collection.parse()
    Path(collection.report["documents"][0]["path"]).unlink()
    assert collection.resumable() == 1
    report = collection.resume()
    assert report["documents"] and Path(report["documents"][0]["path"]).is_file()
    assert report["verification"]["broken"] == 0


def test_the_journal_names_every_file_and_its_outcome(tmp_path):
    folder = tmp_path / "disk"
    write_csv(folder / "a.csv")
    (folder / "ghost.bin").write_bytes(b"\x00opaque")
    collection = Collection(
        folder, tmp_path / "work", build_pack(tmp_path), settings=Settings(threads=1)
    )
    report = collection.parse()
    events = read_journal(collection.output / "journal.jsonl")
    kinds = [event["kind"] for event in events]
    assert kinds[0] == "operation.started" and kinds[-1] == "operation.finished"
    assert "inventory.done" in kinds and "verification.done" in kinds
    done = {Path(event["path"]).name: event for event in events if event["kind"] == "file.done"}
    assert set(done) == {"a.csv", "ghost.bin"}
    assert done["ghost.bin"]["status"] == "unsupported"
    assert all("seconds" in event for event in done.values())
    # One line per file, no file announced twice.
    assert sum(1 for kind in kinds if kind == "file.done") == len(report["files"])
    assert journal_summary(collection.output / "journal.jsonl")["events"] == len(events)
    assert events[-1]["status"] == "complete"


def test_each_analysis_carries_the_verdict_of_the_write_that_made_it(tmp_path):
    folder = tmp_path / "disk"
    write_csv(folder / "a.csv", rows=4)
    collection = Collection(
        folder, tmp_path / "work", build_pack(tmp_path), settings=Settings(threads=1)
    )
    report = collection.parse()
    assert report["verification"] == dict(checked=1, broken=0, unchecked=0)
    document = report["documents"][0]
    assert document["verification"]["status"] == "ok"
    assert document["verification"]["rows"] == document["verification"]["expected"]

    # A check can still be run by hand, and it sees a file that lost a row.
    target = document["path"]
    connection = duckdb.connect(target)
    try:
        rows = connection.execute("SELECT * FROM events").fetchall()
        placeholders = ",".join("?" * len(rows[0]))
        connection.execute("DELETE FROM events")
        connection.executemany(f"INSERT INTO events VALUES ({placeholders})", rows[1:])
    finally:
        connection.close()
    assert verify_analysis(target)["status"] == "mismatch"
    # The report keeps what the write proved, and the summary pass never opens the file:
    # the workspace may be reading it, and a second connection breaks DuckDB.
    assert collection.verify_documents() == dict(checked=1, broken=0, unchecked=0)


def test_a_document_without_a_verdict_is_reported_unchecked(tmp_path):
    folder = tmp_path / "disk"
    write_csv(folder / "a.csv")
    collection = Collection(
        folder, tmp_path / "work", build_pack(tmp_path), settings=Settings(threads=1)
    )
    report = collection.parse()
    report["documents"][0].pop("verification")
    assert collection.verify_documents() == dict(checked=0, broken=0, unchecked=1)


def test_verify_analysis_reports_a_missing_database(tmp_path):
    assert verify_analysis(tmp_path / "nothing.timeline")["status"] == "missing"


def test_summary_counts_are_the_rows_it_shows(tmp_path):
    folder = tmp_path / "disk"
    write_csv(folder / "a.csv")
    (folder / "ghost.bin").write_bytes(b"\x00opaque")
    report = Collection(
        folder, tmp_path / "work", build_pack(tmp_path), settings=Settings(threads=1)
    ).parse()
    summary = report["summary"]
    assert summary["files"] == len(report["files"]) == 2
    assert summary["analyses"] == len(report["documents"]) == 1
    counted = sum(value for key, value in summary.items() if key not in ("files", "analyses"))
    assert counted == summary["files"]
    assert summary["unsupported"] == 1 and summary["complete"] == 1


def test_a_journal_that_cannot_be_written_says_so(tmp_path):
    target = tmp_path / "journal.jsonl"
    target.mkdir()
    journal = ImportJournal(target)
    journal.event("operation.started")
    assert journal.error and journal.count == 0


def test_journal_lines_are_readable_by_a_third_party(tmp_path):
    folder = tmp_path / "disk"
    write_csv(folder / "a.csv")
    collection = Collection(
        folder, tmp_path / "work", build_pack(tmp_path), settings=Settings(threads=1)
    )
    collection.parse()
    with (collection.output / "journal.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            assert set(record) >= {"time", "kind", "elapsed"}


def test_a_memory_retry_is_part_of_the_record(tmp_path, monkeypatch):
    """A run that needed two attempts must not read like a run that needed one."""
    folder = tmp_path / "disk"
    write_csv(folder / "a.csv")
    collection = Collection(
        folder, tmp_path / "work", build_pack(tmp_path), settings=Settings(threads=1, memory_mb=64)
    )
    collection.prepare_output()
    (collection.output / "analyses").mkdir()
    (collection.output / "results").mkdir()
    original = Collection._import_once
    attempts = []

    def flaky(self, *args, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise duckdb.OutOfMemoryException("Out of Memory Error: failed to pin block")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Collection, "_import_once", flaky)
    monkeypatch.setattr("fireblade.core.collection.grown_memory", lambda memory: memory * 2)
    document = collection.import_result(folder / "a.csv", "native", register=False)
    assert Path(document["path"]).is_file()
    retries = [
        event
        for event in read_journal(collection.output / "journal.jsonl")
        if event["kind"] == "import.retry"
    ]
    assert retries and retries[0]["attempt"] == 1 and retries[0]["memory_mb"] == 128
