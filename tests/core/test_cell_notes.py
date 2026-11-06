"""Notes on a single cell: saved, editable, and kept when the analysis is reopened."""
import csv

import duckdb
import pytest

from fireblade.core.engine import Case, View


@pytest.fixture
def case(tmp_path):
    source = tmp_path / "source.csv"
    with source.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Time", "Artifact", "User", "ID", "Description"])
        writer.writerows([
            ["2026-01-02 12:00:00", "MFT", "alice", "001", "first"],
            ["2026-01-01 12:00:00", "EVTX", "bob", "10", "second"],
            ["2026-01-03 12:00:00", "MFT", "alice", "2", "third"],
        ])
    analysis = Case(tmp_path / "analysis.timeline", memory_mb=256)
    analysis.import_csv(source)
    yield analysis
    analysis.close()


def test_a_cell_note_is_saved_and_read_back(case):
    case.bookmark(2, "the user field", column=2)
    assert case.cell_notes() == {(2, 2): "the user field"}
    assert case.bookmarks() == {}, "a cell note is not a row bookmark"


def test_a_cell_note_survives_reopening_the_analysis(case):
    """The note a user writes must still be there the next time they open the cell."""
    path = case.path
    case.bookmark(2, "written once", column=2)
    case.close()
    reopened = Case(path, memory_mb=256)
    try:
        assert reopened.cell_notes({2}) == {(2, 2): "written once"}
        reopened.bookmark(2, "edited", column=2)
        assert reopened.cell_notes({2}) == {(2, 2): "edited"}
        reopened.bookmark(2, None, column=2)
        assert reopened.cell_notes({2}) == {}
    finally:
        reopened.close()
    case.db = duckdb.connect(":memory:")     # the fixture closes it again


def test_a_row_note_and_a_cell_note_live_together(case):
    case.bookmark(2, "the row")
    case.bookmark(2, "the cell", column=3)
    assert case.bookmarks() == {2: "the row"}
    assert case.cell_notes() == {(2, 3): "the cell"}

    case.bookmark(2, None)                   # removing the row note
    assert case.bookmarks() == {}
    assert case.cell_notes() == {(2, 3): "the cell"}, "the cell note must survive"


def test_the_cell_note_does_not_leak_into_another_cell(case):
    case.bookmark(2, "only here", column=2)
    notes = case.cell_notes({2})
    assert (2, 2) in notes and (2, 3) not in notes


def test_an_analysis_written_before_cell_notes_is_migrated(tmp_path):
    """An older file keeps its row notes and gains the per-cell table."""
    source = tmp_path / "source.csv"
    source.write_text("Time,User\n2026-01-01 00:00:00,alice\n", encoding="utf-8")
    path = tmp_path / "old.timeline"
    analysis = Case(path, memory_mb=256)
    analysis.import_csv(source)
    analysis.bookmark(1, "an old note")
    analysis.close()

    connection = duckdb.connect(str(path))
    connection.execute("CREATE TABLE legacy_notes (row_id BIGINT PRIMARY KEY, note VARCHAR)")
    connection.execute("INSERT INTO legacy_notes SELECT row_id, note FROM bookmarks")
    connection.execute("DROP TABLE bookmarks")
    connection.execute("ALTER TABLE legacy_notes RENAME TO bookmarks")
    connection.close()

    migrated = Case(path, memory_mb=256)
    try:
        columns = [row[0] for row in migrated.db.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='bookmarks'").fetchall()]
        assert "column_id" in columns
        assert migrated.bookmarks() == {1: "an old note"}
        migrated.bookmark(1, "a new cell note", column=1)
        assert migrated.cell_notes() == {(1, 1): "a new cell note"}
    finally:
        migrated.close()
