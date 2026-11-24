"""An annotation export must never hand over an empty file in silence."""

import csv

import pytest

from fireblade.core.engine import Case
from fireblade.core.models import Filter, View


def build(tmp_path):
    source = tmp_path / "input.csv"
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["ID", "Name"])
        for index in range(1, 21):
            writer.writerow([str(index), f"row {index}"])
    case = Case(tmp_path / "case.timeline", memory_mb=64, threads=1)
    case.import_csv(source)
    return case


def test_annotation_export_refuses_a_filter_that_hides_every_note(tmp_path):
    case = build(tmp_path)
    try:
        case.bookmark(6, "vue trois fois")
        view = View(filters=[Filter(0, "eq", "1")])
        view.bookmarks_only = True
        with pytest.raises(ValueError) as failure:
            case.export(tmp_path / "notes.csv", view, include_annotations=True)
        assert "no annotated row matches the current view" in str(failure.value)
        assert "holds 1 annotation" in str(failure.value)
        assert not (tmp_path / "notes.csv").exists(), "an empty export must leave no file behind"
    finally:
        case.close()


def test_annotation_export_refuses_an_analysis_without_notes(tmp_path):
    case = build(tmp_path)
    try:
        view = View()
        view.bookmarks_only = True
        with pytest.raises(ValueError) as failure:
            case.export(tmp_path / "notes.csv", view, include_annotations=True)
        assert "holds no annotation" in str(failure.value)
    finally:
        case.close()


def test_annotation_export_writes_the_note_when_the_view_allows_it(tmp_path):
    case = build(tmp_path)
    try:
        case.bookmark(6, "vue trois fois")
        view = View()
        view.bookmarks_only = True
        receipt = case.export(tmp_path / "notes.csv", view, include_annotations=True)
        assert receipt["written"] == 1
        with (tmp_path / "notes.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        assert len(rows) == 2
        assert rows[-1][-1] == "vue trois fois"
        assert rows[-1][-2] == "True"
    finally:
        case.close()
